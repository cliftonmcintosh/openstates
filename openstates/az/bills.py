import json
import datetime

from pupa.scrape import Scraper, Bill
from . import utils
from . import action_utils
from . import session_metadata

from lxml import html


BASE_URL = 'http://www.azleg.gov/'


class AZBillScraper(Scraper):
    chamber_map = {'lower': 'H', 'upper': 'S'}
    chamber_map_rev = {'H': 'upper', 'S': 'lower', 'G': 'executive', 'SS': 'executive'}
    chamber_map_rev_eng = {'H': 'House', 'S': 'Senate', 'G': 'Governor',
                           'SS': 'Secretary of State'}

    def scrape_bill(self, chamber, session, bill_id, session_id):
        """
        Scrapes documents, actions, vote counts and votes for
        a given bill.
        """
        bill_json_url = 'https://apps.azleg.gov/api/Bill/?billNumber={}&sessionId={}&' \
                        'legislativeBody={}'.format(bill_id, session_id, self.chamber_map[chamber])
        response = self.get(bill_json_url)
        # print(response.content)
        page = json.loads(response.content.decode('utf-8'))

        bill_title = page['ShortTitle']
        bill_id = page['Number']
        internal_id = page['BillId']
        bill_type = self.get_bill_type(bill_id)
        bill = Bill(
            bill_id,
            legislative_session=session,
            chamber=chamber,
            title=bill_title,
            classification=bill_type,
        )

        bill = self.scrape_actions(bill, page, chamber)
        bill = self.scrape_versions(bill, internal_id)
        bill = self.scrape_sponsors(bill, internal_id)
        bill = self.scrape_subjects(bill, internal_id)

        bill_url = 'https://apps.azleg.gov/BillStatus/BillOverview/{}?SessionId={}'.format(
                    internal_id, session_id)
        bill.add_source(bill_url)

        bill = self.sort_bill_actions(bill)

        yield bill

    def scrape_versions(self, bill, internal_id):
        # Careful, this sends XML to a browser but JSON to machines
        # https://apps.azleg.gov/api/DocType/?billStatusId=68408
        versions_url = 'https://apps.azleg.gov/api/DocType/?billStatusId={}'.format(internal_id)
        page = json.loads(self.get(versions_url).content.decode('utf-8'))
        if page and 'Documents' in page[0]:
            for doc in page[0]['Documents']:
                if doc['HtmlPath']:
                    bill.add_version_link(
                        note=doc['DocumentName'],
                        url=doc['HtmlPath'],
                        media_type='text/html'
                    )
                elif doc['PdfPath']:
                    bill.add_version_link(
                        note=doc['DocumentName'],
                        url=doc['PdfPath'],
                        media_type='application/pdf'
                    )
                else:
                    self.warning("No PDF or HTML version found for %s" % doc['DocumentName'])
        return bill

    def scrape_sponsors(self, bill, internal_id):
        # Careful, this sends XML to a browser but JSON to machines
        # https://apps.azleg.gov/api/BillSponsor/?id=68398
        sponsors_url = 'https://apps.azleg.gov/api/BillSponsor/?id={}'.format(internal_id)
        page = json.loads(self.get(sponsors_url).content.decode('utf-8'))
        for sponsor in page:
            if 'Prime' in sponsor['SponsorType']:
                sponsor_type = 'primary'
            else:
                sponsor_type = 'cosponsor'

        # Some older bills don't have the FullName key
        if 'FullName' in sponsor['Legislator']:
            sponsor_name = sponsor['Legislator']['FullName']
        else:
            sponsor_name = "{} {}".format(
                sponsor['Legislator']['FirstName'],
                sponsor['Legislator']['LastName'],
            )
        bill.add_sponsorship(
            classification=str(sponsor_type),
            name=sponsor_name,
            entity_type='person',
            primary=sponsor_type == 'primary'
        )
        return bill

    def scrape_subjects(self, bill, internal_id):
        # https://apps.azleg.gov/api/Keyword/?billStatusId=68149
        subjects_url = 'https://apps.azleg.gov/api/Keyword/?billStatusId={}'.format(internal_id)
        page = json.loads(self.get(subjects_url).content.decode('utf-8'))
        for subject in page:
            bill.add_subject(subject['Name'])
        return bill

    def scrape_actions(self, bill, page, self_chamber):
        """
        Scrape the actions for a given bill

        AZ No longer provides a full list, just a series of keys and dates.
        So map that backwards using action_map
        """
        for status in page['BillStatusAction']:
            if status['Action'] in action_utils.status_action_map:
                category = action_utils.status_action_map[status['Action']]
                if status['Committee']['TypeName'] == 'Floor':
                    categories = [category]
                    if status['Committee']['CommitteeShortName'] == 'THIRD':
                        categories.append('reading-3')
                elif status['Committee']['TypeName'] == 'Standing':
                    categories = ['committee-{}'.format(category)]
                else:
                    raise ValueError(
                        'Unexpected committee type: {}'.format(status['Committee']['TypeName']))
                action_date = datetime.datetime.strptime(
                    status['ReportDate'], '%Y-%m-%dT%H:%M:%S').strftime('%Y-%m-%d')
                bill.add_action(
                    description=status['Action'],
                    chamber={
                        'S': 'upper',
                        'H': 'lower',
                    }[status['Committee']['LegislativeBody']],
                    date=action_date,
                    classification=categories,
                )
        for action in action_utils.action_map:
            if page[action] and action_utils.action_map[action]['name'] != '':
                try:
                    action_date = datetime.datetime.strptime(
                        page[action], '%Y-%m-%dT%H:%M:%S').strftime('%Y-%m-%d')

                    bill.add_action(
                        chamber=self.actor_from_action(bill, action, self_chamber),
                        description=action_utils.action_map[action]['name'],
                        date=action_date,
                        classification=action_utils.action_map[action]['action'],
                    )
                except ValueError:
                    self.info("Invalid Action Time {} for {}".format(page[action], action))

        # Governor Signs and Vetos get different treatment
        if page['GovernorAction'] == 'Signed':
            action_date = page['GovernorActionDate'].split('T')[0]
            bill.add_action(
                chamber='executive',
                description='Signed by Governor',
                date=action_date,
                classification='executive-signature',
            )

        if page['GovernorAction'] == 'Vetoed':
            action_date = page['GovernorActionDate'].split('T')[0]
            bill.add_action(
                chamber='executive',
                description='Vetoed by Governor',
                date=action_date,
                classification='executive-veto',
            )

        # Transmit to (X) has its own data structure as well
        for transmit in page['BodyTransmittedTo']:
            action_date = transmit['TransmitDate'].split('T')[0]
            # upper, lower, executive
            action_actor = self.chamber_map_rev[transmit['LegislativeBody']]
            # house, senate, governor
            body_text = self.chamber_map_rev_eng[transmit['LegislativeBody']]

            action_text = 'Transmit to {}'.format(body_text)

            if action_actor == 'executive':
                action_type = 'executive-receipt'
            else:
                action_type = None

            bill.add_action(
                chamber=action_actor,
                description=action_text,
                date=action_date,
                classification=action_type
            )

        return bill

    def actor_from_action(self, bill, action, self_chamber):
        """
        Determine the actor from the action key
        If the action_map = 'chamber', return the bill's home chamber
        """
        action_map = action_utils.action_chamber_map
        for key in action_map:
            if key in action:
                if action_map[key] == 'chamber':
                    return self_chamber
                else:
                    return action_map[key]

    def scrape(self, chamber=None, session=None):
        if not session:
            session = self.latest_session()
            self.info('no session specified, using %s', session)
        session_id = session_metadata.session_id_meta_data[session]

        # Get the bills page to start the session
        req = self.get('http://www.azleg.gov/bills/')

        session_form_url = 'http://www.azleg.gov/azlegwp/setsession.php'
        form = {
            'sessionID': session_id
        }
        req = self.post(url=session_form_url, data=form, cookies=req.cookies, allow_redirects=True)

        bill_list_url = 'http://www.azleg.gov/bills/'

        page = self.get(bill_list_url, cookies=req.cookies).content
        # There's an errant close-comment that browsers handle
        # but LXML gets really confused.
        page = page.replace(b'--!>', b'-->')
        page = html.fromstring(page)

        bill_rows = []
        chambers = [chamber] if chamber else ['upper', 'lower']
        for chamber in chambers:
            if chamber == 'lower':
                bill_rows = page.xpath('//div[@name="HBTable"]//tbody//tr')
            else:
                bill_rows = page.xpath('//div[@name="SBTable"]//tbody//tr')
            for row in bill_rows:
                bill_id = row.xpath('td/a/text()')[0]
                yield from self.scrape_bill(chamber, session, bill_id, session_id)

        # TODO: MBTable - Non-bill Misc Motions?

    def sort_bill_actions(self, bill):
        actions = bill.actions
        actions_list = []
        out_of_order = []
        new_list = []
        if not actions:
            return bill
        action_date = actions[0]['date']
        actions[0]['description'] = actions[0]['description'].lower()
        actions_list.append(actions[0])
        # seperate the actions that are out of order
        for action in actions[1:]:
            if action['date'] < action_date:
                out_of_order.append(action)
            else:
                actions_list.append(action)
                action_date = action['date']
            action['description'] = action['description'].lower()
        action_date = actions_list[0]['date']

        for action in actions_list:
            # this takes care of the actions in beween
            for act in out_of_order:
                if act['date'] < action_date:
                    o_index = out_of_order.index(act)
                    new_list.append(out_of_order.pop(o_index))
                if act['date'] >= action_date and act['date'] < action['date']:
                    o_index = out_of_order.index(act)
                    new_list.append(out_of_order.pop(o_index))
            new_list.append(action)

            for act in out_of_order:
                if act['date'] == action['date']:
                    o_index = out_of_order.index(act)
                    new_list.append(out_of_order.pop(o_index))

        if out_of_order != []:
            self.info("Unable to sort " + bill.identifier)
            return bill
        else:
            bill.actions = new_list
            return bill

    def get_bill_type(self, bill_id):
        for key in utils.bill_types:
            if key in bill_id.lower():
                return utils.bill_types[key]
        return None

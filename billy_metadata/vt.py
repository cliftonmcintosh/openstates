metadata = dict(
    name='Vermont',
    abbreviation='vt',
    capitol_timezone='America/New_York',
    legislature_name='Vermont General Assembly',
    legislature_url='http://legislature.vermont.gov/',
    chambers = {
        'upper': {'name': 'Senate', 'title': 'Senator', 'term': 2},
        'lower': {'name': 'House', 'title': 'Representative', 'term': 2},
    },
    terms=[{'name': '2009-2010',
            'start_year': 2009,
            'end_year': 2010,
            'sessions': ['2009-2010']},
           {'name': '2011-2012',
            'start_year': 2011,
            'end_year': 2012,
            'sessions': ['2011-2012']},
           {'name': '2013-2014',
            'start_year': 2013,
            'end_year': 2014,
            'sessions': ['2013-2014']},
           {'name': '2015-2016',
            'start_year': 2015,
            'end_year': 2016,
            'sessions': ['2015-2016']},
           {'name': '2017-2018',
            'start_year': 2017,
            'end_year': 2018,
            'sessions': ['2017-2018']},
           ],
    session_details={'2009-2010': {'type': 'primary',
                                   'display_name': '2009-2010 Regular Session',
                                   '_scraped_name': '2009-2010 Session',
                                  },
                     '2011-2012': {'type': 'primary',
                                   'display_name': '2011-2012 Regular Session',
                                   '_scraped_name': '2011-2012 Session',
                                  },
                     '2013-2014': {'type': 'primary',
                                   'display_name': '2013-2014 Regular Session',
                                   '_scraped_name': '2013-2014 Session',
                                  },
                     '2015-2016': {'type': 'primary',
                                   'display_name': '2015-2016 Regular Session',
                                   '_scraped_name': '2015-2016 Session',
                                  },
                     '2017-2018': {'type': 'primary',
                                   'display_name': '2017-2018 Regular Session',
                                   '_scraped_name': '2017-2018 Session',
                                  },
                     },
    feature_flags=[],
    _ignored_scraped_sessions= ['2009 Special Session']
)

"""Source definitions for the three fixture boards, written to drive the leaves in stage 4.

These are test inputs, not composition's definitions: they follow the declared source shape and
point at run 2's saved fixtures, so leaves can be run on real postings without the network.
"""

GREENHOUSE = {
    "id": "greenhouse:gitlab", "company": "GitLab",
    "endpoint": "https://boards-api.greenhouse.io/v1/boards/gitlab/jobs?content=true", "headers": {},
    "list_path": "jobs", "id_path": "id",
    "date": {"path": "first_published", "format": "iso8601"},
    "fields": {
        "title": [{"path": "title"}],
        "link": [{"path": "absolute_url"}],
        "location": [{"path": "location.name"}, {"path": "offices[].name"}],
        "department_team": [{"path": "departments[].name"}],
        "full_text": [{"path": "content", "format": "escaped_html"}],
    },
}

LEVER = {
    "id": "lever:spotify", "company": "Spotify",
    "endpoint": "https://api.lever.co/v0/postings/spotify?mode=json", "headers": {},
    "list_path": None, "id_path": "id",
    "date": {"path": "createdAt", "format": "epoch_millis"},
    "fields": {
        "title": [{"path": "text"}],
        "link": [{"path": "hostedUrl"}],
        "location": [{"path": "categories.allLocations[]"}, {"path": "categories.location"}],
        "department_team": [{"path": "categories.department"}, {"path": "categories.team"}],
        "full_text": [{"path": "descriptionPlain"}, {"path": "lists[].text"},
                      {"path": "lists[].content", "format": "html"}, {"path": "additionalPlain"}],
        "countries": [{"path": "country"}],
        "work_arrangement": [{"path": "workplaceType",
                              "values": {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite"}}],
        "employment_type": [{"path": "categories.commitment",
                             "values": {"Permanent": "full-time", "Full-time": "full-time",
                                        "Part-time": "part-time", "Intern": "internship"}}],
    },
}

ASHBY = {
    "id": "ashby:linear", "company": "Linear",
    "endpoint": "https://api.ashbyhq.com/posting-api/job-board/linear?includeCompensation=true",
    "headers": {"User-Agent": "job-triage/2"},
    "list_path": "jobs", "id_path": "id",
    "date": {"path": "publishedAt", "format": "iso8601"},
    "fields": {
        "title": [{"path": "title"}],
        "link": [{"path": "jobUrl"}],
        "location": [{"path": "location"}, {"path": "secondaryLocations[].location"}],
        "department_team": [{"path": "department"}, {"path": "team"}],
        "full_text": [{"path": "descriptionHtml", "format": "html"}],
        "countries": [{"path": "address.postalAddress.addressCountry"},
                      {"path": "secondaryLocations[].address.postalAddress.addressCountry"}],
        "work_arrangement": [{"path": "workplaceType",
                              "values": {"Remote": "remote", "Hybrid": "hybrid", "OnSite": "onsite"}},
                             {"path": "isRemote", "values": {"true": "remote"}}],
        "employment_type": [{"path": "employmentType",
                             "values": {"FullTime": "full-time", "PartTime": "part-time",
                                        "Intern": "internship", "Contract": "contract",
                                        "Temporary": "temporary"}}],
    },
}

BOARDS = [("greenhouse-gitlab.json", GREENHOUSE), ("lever-spotify.json", LEVER), ("ashby-linear.json", ASHBY)]

PAY_FLOORS = {"USD": 15080, "EUR": 20000, "GBP": 22000}

"""The two GraphQL documents this adapter sends, and the headers it sends them with.

The selection set below names only the fields `normalize.py` maps, which is roughly a tenth of what
the site's own page asks for. That is deliberate: every field named here is a field that can change
shape and break a run, so the smallest set that answers the question is also the most durable one,
and every field in it can be pointed at a use.
"""

from __future__ import annotations

ENDPOINT = "https://www.realtor.com/frontdoor/graphql"

#: The endpoint refuses a request without a client-identification pair (`HTTP 400 missing client
#: identification headers`), so sending nothing but an honest user agent is not on offer. What IS
#: on offer is an honest *value*: it accepts `homescout` here exactly as it accepts its own web
#: app's name.
#:
#: This is the rule for every adapter, not a quirk of this one. A header may be sent because the
#: source requires it. Its value must name this tool. No header value may name another product,
#: which rules out the browser user agent, the platform claims, and the `x-is-bot: false` that the
#: obvious reference implementation ships with.
CLIENT_NAME = "homescout"


def headers(version: str) -> dict[str, str]:
    return {
        "rdc-client-name": CLIENT_NAME,
        "rdc-client-version": version,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


#: Everything the store keeps, and nothing else. Notably absent: the advertiser block, open houses,
#: estimates, pet policy, HOA, tags, unit lists. If one of those is ever wanted, it is one line here
#: and one line in the mapping.
HOME_FIELDS = """
  property_id
  listing_id
  status
  mls_status
  list_price
  list_date
  last_update_date
  href
  permalink
  description { type sqft beds baths_full baths_half lot_sqft year_built text }
  location {
    address {
      line unit city state_code postal_code
      coordinate { lat lon }
    }
    county { name }
  }
  tax_record { apn tax_parcel_id }
  primary_photo { href }
  photos { href }
"""

GEOGRAPHY_QUERY = """
query Search_suggestions($searchInput: SearchSuggestionsInput!) {
  search_suggestions(search_input: $searchInput) {
    geo_results {
      text
      geo {
        area_type
        city
        state_code
        postal_code
        county
        mpr_id
        centroid { lat lon }
      }
    }
  }
}
"""

#: Two shapes, because a named place and a point-with-a-radius are different queries to this source.
#: The filters and the date bound are interpolated from the capability declaration, so a filter the
#: adapter never declared has no way into either string.
AREA_SEARCH = """
query GetHomeSearch($search_location: SearchLocation, $offset: Int) {
  homeSearch: home_search(
    query: {
      search_location: $search_location
      %(status)s
      %(dates)s
      %(types)s
      %(filters)s
    }
    bucket: { sort: "fractal_v1.1.3_fr" }
    limit: %(limit)d
    offset: $offset
  ) {
    count
    total
    results { %(fields)s }
  }
}
"""

RADIUS_SEARCH = """
query GetHomeSearch($coordinates: [Float]!, $radius: String!, $offset: Int) {
  homeSearch: home_search(
    query: {
      nearby: { coordinates: $coordinates radius: $radius }
      %(status)s
      %(dates)s
      %(types)s
      %(filters)s
    }
    bucket: { sort: "fractal_v1.1.3_fr" }
    limit: %(limit)d
    offset: $offset
  ) {
    count
    total
    results { %(fields)s }
  }
}
"""


def minified(document: str) -> str:
    """Collapse a document to one line. The endpoint is happier with it and it travels smaller."""
    return " ".join(document.split())

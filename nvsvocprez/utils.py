import logging
from typing import Dict, List, Literal
import httpx
import config
from config import DATA_URI, ORDS_ENDPOINT_URL
import pickle
from pathlib import Path
import requests
from pyldapi.data import RDF_MEDIATYPES

from pyldapi.profile import Profile



api_home_dir = Path(__file__).parent
collections_pickle = Path(api_home_dir / "cache" / "collections.pickle")
conceptschemes_pickle = Path(api_home_dir / "cache" / "conceptschemes.pickle")


class TriplestoreError(Exception):
    pass


def sparql_query(query: str):
    r = httpx.post(
        config.SPARQL_ENDPOINT,
        data=query,
        headers={"Content-Type": "application/sparql-query"},
        auth=(config.SPARQL_USERNAME, config.SPARQL_PASSWORD),
        timeout=60.0,
    )
    if 200 <= r.status_code < 300:
        return True, r.json()["results"]["bindings"]
    else:
        return False, r.status_code, r.text


def sparql_construct(query: str, rdf_mediatype="text/turtle"):
    r = httpx.post(
        config.SPARQL_ENDPOINT,
        data=query,
        headers={"Content-Type": "application/sparql-query", "Accept": rdf_mediatype},
        auth=(config.SPARQL_USERNAME, config.SPARQL_PASSWORD),
        timeout=60.0,
    )
    if 200 <= r.status_code < 300:
        return True, r.content
    else:
        return False, r.status_code, r.text


def cache_clear():
    logging.debug("cleared cache")
    if collections_pickle.is_file():
        collections_pickle.unlink()
    if conceptschemes_pickle.is_file():
        conceptschemes_pickle.unlink()


def cache_fill(
    collections_or_conceptschemes_or_both: Literal[
        "collections", "conceptschemes", "both"
    ] = "both"
):
    logging.debug(f"filled cache {collections_or_conceptschemes_or_both}")
    if not Path(api_home_dir / "cache").is_dir():
        Path(api_home_dir / "cache").mkdir()

    if collections_or_conceptschemes_or_both == "collections":
        q = """
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dcterms: <http://purl.org/dc/terms/>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT ?uri ?id ?systemUri ?prefLabel ?created ?issued ?modified ?creator ?publisher ?license
            (GROUP_CONCAT(?conformsto;SEPARATOR=",") AS ?conforms_to) ?versionInfo ?description ?registermanager ?registerowner ?seeAlso
            WHERE {
                ?uri a skos:Collection .
                BIND (STRAFTER(STRBEFORE(STR(?uri), "/current/"), "/collection/") AS ?id)
                BIND (STRAFTER(STR(?uri), ".uk") AS ?systemUri)
                OPTIONAL { ?uri skos:prefLabel ?prefLabel .
                    FILTER(lang(?prefLabel) = "en" || lang(?prefLabel) = "")
                }
                OPTIONAL { ?uri dcterms:created ?created }
                OPTIONAL { ?uri dcterms:issued ?issued }
                OPTIONAL {
                    ?uri dcterms:date ?m .
                    BIND (SUBSTR(?m, 0, 11) AS ?modified)
                }
                OPTIONAL { ?uri dcterms:creator ?creator }
                OPTIONAL { ?uri dcterms:publisher ?publisher }
                OPTIONAL { ?uri dcterms:license ?license }
                OPTIONAL { ?uri dcterms:conformsTo ?conformsto }
                OPTIONAL { ?uri owl:versionInfo ?versionInfo }
                OPTIONAL { ?uri dcterms:description ?description .
                    FILTER(lang(?description) = "en" || lang(?description) = "")
                }
                # NVS special properties
                OPTIONAL {
                    ?uri <http://www.isotc211.org/schemas/grg/RE_RegisterManager> ?registermanager .
                    ?uri <http://www.isotc211.org/schemas/grg/RE_RegisterOwner> ?registerowner .
                }
                OPTIONAL { ?uri rdfs:seeAlso ?seeAlso }
            }
group by ?uri ?id ?systemUri ?prefLabel ?created ?issued ?modified ?creator ?publisher ?license ?versionInfo ?description ?registermanager ?registerowner ?seeAlso
            ORDER BY ?prefLabel 
            """

        collections_json = sparql_query(q)
        if collections_json[0]:  # i.e. we got no error
            with open(collections_pickle, "wb") as cache_file:
                pickle.dump(collections_json[1], cache_file)
        else:
            raise TriplestoreError(
                f"The call to fill the Collections index cache failed. Status Code: {collections_json[1]} , "
                f"Error: {collections_json[2]}"
            )
    elif collections_or_conceptschemes_or_both == "conceptschemes":
        q = """
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dcterms: <http://purl.org/dc/terms/>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT ?uri ?id ?systemUri ?prefLabel ?modified ?creator ?publisher ?versionInfo ?description
            WHERE {
                ?uri a skos:ConceptScheme .
                BIND (STRAFTER(STRBEFORE(STR(?uri), "/current/"), "/scheme/") AS ?id)
                BIND (STRAFTER(STR(?uri), ".uk") AS ?systemUri)
                OPTIONAL { ?uri skos:prefLabel ?prefLabel .
                    FILTER(lang(?prefLabel) = "en" || lang(?prefLabel) = "") 
                }
                OPTIONAL { 
                    ?uri dcterms:date ?m .
                    BIND (SUBSTR(?m, 0, 11) AS ?modified)
                }
                OPTIONAL { ?uri dcterms:creator ?creator }
                OPTIONAL { ?uri dcterms:publisher ?publisher }
                OPTIONAL { ?uri owl:versionInfo ?versionInfo }
                OPTIONAL { ?uri dcterms:description ?description .
                    FILTER(lang(?description) = "en" || lang(?description) = "") 
                }
            }
            ORDER BY ?prefLabel
            """

        conceptschemes_json = sparql_query(q)
        if conceptschemes_json[0]:  # i.e. we got no error
            with open(conceptschemes_pickle, "wb") as cache_file:
                pickle.dump(conceptschemes_json[1], cache_file)
        else:
            raise TriplestoreError(
                f"The call to fill the Concept Schemes index cache failed. Status Code: {conceptschemes_json[1]} , "
                f"Error: {conceptschemes_json[2]}"
            )
    else:  # both
        pass


def cache_return(
    collections_or_conceptschemes: Literal["collections", "conceptschemes"]
) -> dict:
    if collections_or_conceptschemes == "collections":
        if not collections_pickle.is_file():
            cache_fill(collections_or_conceptschemes_or_both="collections")

        with open(collections_pickle, "rb") as cache_file:
            return pickle.load(cache_file)

    elif collections_or_conceptschemes == "conceptschemes":
        if not conceptschemes_pickle.is_file():
            cache_fill(collections_or_conceptschemes_or_both="conceptschemes")

        with open(conceptschemes_pickle, "rb") as cache_file:
            return pickle.load(cache_file)

    def draw_concept_hierarchy(hierarchy):
        tab = "\t"
        previous_length = 1

        text = ""
        tracked_items = []
        for item in hierarchy:
            mult = None

            if item[0] > previous_length + 2:  # SPARQL query error on length value
                for tracked_item in tracked_items:
                    if tracked_item["name"] == item[3]:
                        mult = tracked_item["indent"] + 1

            if mult is None:
                found = False
                for tracked_item in tracked_items:
                    if tracked_item["name"] == item[3]:
                        found = True
                if not found:
                    mult = 0

            if mult is None:  # else: # everything is normal
                mult = item[0] - 1

            t = tab * mult + "* [" + item[2] + "](" + get_content_uri(item[1]) + ")\n"
            text += t
            previous_length = mult
            tracked_items.append({"name": item[1], "indent": mult})

        return markdown.markdown(text)


def render_concept_tree(html_doc):
    soup = BeautifulSoup(html_doc, "html.parser")

    # concept_hierarchy = soup.find(id='concept-hierarchy')

    uls = soup.find_all("ul")

    for i, ul in enumerate(uls):
        # Don't add HTML class nested to the first 'ul' found.
        if not i == 0:
            ul["class"] = "nested"
            if ul.parent.name == "li":
                temp = BeautifulSoup(str(ul.parent.a.extract()), "html.parser")
                ul.parent.insert(
                    0, BeautifulSoup('<span class="caret">', "html.parser")
                )
                ul.parent.span.insert(0, temp)
    return soup


def get_accepts(accept_header: str):
    return [
        accept.split(";")[0].replace("*/*", "text/html")
        for accept in accept_header.split(",")
    ]

def exists_triple(s: str):
  query = f"select count(*) where {{ <{DATA_URI + s}> ?p ?o .}}"
  rr = sparql_query(query)
  count = rr[1][0]['.1'].get('value')
  return True if bool(int(count)) else False


def get_alt_profiles() -> Dict:
    """Get alt profiles from livbodcsos ords endpoint.
    
        Returns (Dict): Dict of parsed alt profile data. {[ alt_profile_url : {alt_profile_object}, ...]}.
    """
    if ORDS_ENDPOINT_URL is None:
        logging.error("Environment variable ORDS_ENDPOINT_URL is not set.")
        return {}
    try:
        url = f"{ORDS_ENDPOINT_URL}/webtabsn/nvs/altprof"
        resp_json = requests.get(url).json()
        altprof_data_by_url = {alt["url"]: alt for alt in resp_json['items']}
        return altprof_data_by_url
    except requests.RequestException as exc: 
        logging.error("Failed to retrieve alternate profile information from %s.\n%s", url, exc)
        return {}   # Return blank list to avoid internal server error.
    
    
    
def get_alt_profile_objects(
    collection:Dict, 
    alt_profiles:Dict, 
    media_types:List=RDF_MEDIATYPES, 
    default_mediatype:str="text/turtle"
    ) -> Dict:
    """Generate Profile objects for all alt profiles.
    
    Args:
        collection (Dict): Dict representing collection data.
        alt_profiles(Dict): Dict of alt profiles { uri : {profile_data}, ...}.
        media_types (List[str]): List of mediatypes for alt profiles.
        default_mediatype (str): Default media type for alt profiles.
        
    Returns:
        Dict: Dict of Profile objects representing each alternate profile.
            { profile_name: ProfileObject, ... }
    """
    profiles = {}
    for url, alt in alt_profiles.items():
        if "conforms_to" in collection and url in collection["conforms_to"]["value"]:
            p = Profile(
                uri=url,
                id=alt['token'],
                label=alt['name'],
                comment=alt['vocprezdesc'],
                mediatypes=media_types,
                default_mediatype=default_mediatype,
                languages=["en"],
                default_language="en",
            )
            profiles[alt['token']] = p
    return profiles


def get_collection_query(profile: Profile, instance_uri: str, exclude_profiles: list):
    """Method to generate a query for the collections page excluding certain profiles.
    
    Args:
        profile_name (Profile): Profile object representing the current profile.
        insance_uri (str): Instance URI.
        exclude_profiles: List of profile URI's to be excluded from query.
    Returns:
        str: The construncted sparql query.
    """
    
    prefix_text = ""
    filter_text = ""
    if profile.id != "nvs":
        # Build prefix text.
        prefix_text += f'PREFIX {profile.id}: <{profile.uri}#>'
        filter_text += """
            FILTER ( ?p2 != skos:broader )
            FILTER ( ?p2 != skos:narrower )
            FILTER ( ?p2 != skos:related )
            FILTER ( ?p2 != owl:sameAs )
        """
    
    for profile in exclude_profiles:
        # Build filter text.
        filter_text += f'FILTER (!STRSTARTS(STR(?p2), "{profile}"))\n'
    
    query = f"""
        PREFIX dc: <http://purl.org/dc/terms/>
        PREFIX dce: <http://purl.org/dc/elements/1.1/>
        PREFIX grg: <http://www.isotc211.org/schemas/grg/>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX pav: <http://purl.org/pav/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX void: <http://rdfs.org/ns/void#>
        {prefix_text}
        CONSTRUCT {{
            <{instance_uri}> ?p ?o .
            <{instance_uri}> skos:member ?m .
            ?m ?p2 ?o2 .
        }}
        WHERE {{
            {{
            <{instance_uri}> ?p ?o .
            MINUS {{ <{instance_uri}> skos:member ?o . }}
            }}
            {{
            <{instance_uri}> skos:member ?m .
            ?m a skos:Concept .
            ?m ?p2 ?o2 .
            FILTER ( ?p2 != skos:broaderTransitive )
            FILTER ( ?p2 != skos:narrowerTransitive )
            {filter_text}   
            }}
        }}
    """
    return query

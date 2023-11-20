from collections import Counter

from neo4j import Driver
from tqdm import tqdm


def add_characters_to_neo4j(driver: Driver, characters: list[dict]) -> None:
    """Add characters to the graph database.

    Args:
        driver (Driver): Neo4j driver
        chapter_characters (list[dict]): List of characters for each chapter
    """
    entity_query = """
    UNWIND $data as row
    MERGE (c:Character {name: row.title})
    SET c.url = row.href
    SET c.aliases = row.aliases
    SET c.blood = row.blood_status
    SET c.nationality = row.nationality
    SET c.species = row.species
    SET c.gender = row.gender
    FOREACH (h in CASE WHEN row.house IS NOT NULL THEN [1] ELSE [] END | MERGE (house:House {name: row.house}) MERGE (c)-[:BELONGS_TO]->(house))
    FOREACH (loyalty IN row.loyalties | MERGE (l:Group {name: loyalty}) MERGE (c)-[:LOYALTY_TO]->(l))
    FOREACH (rel IN row.family_relations | MERGE (f:Character {name: rel.person}) MERGE (c)-[t:FAMILY_MEMBER]->(f) SET t.type = rel.type)
    """

    with driver.session() as session:
        session.run(
            entity_query,
            data=characters,
        )


def add_interactions_to_neo4j(driver: Driver, interactions: Counter) -> None:
    """Add interactions to the graph database.

    Args:
        driver (Driver): Neo4j driver
        distances (Counter): Counter of interactions between characters
    """
    data = [
        {"source": el[0], "target": el[1], "weight": interactions[el]}
        for el in interactions
    ]
    with driver.session() as session:
        session.run(
            """
    UNWIND $data as row
    MERGE (c:Character{name:row.source})
    MERGE (t:Character{name:row.target})
    MERGE (c)-[i:INTERACTS]-(t)
    SET i.weight = coalesce(i.weight,0) + row.weight
    """,
            {"data": data},
        )


def add_metrics_to_neo4j(driver: Driver, metrics: list[dict]) -> None:
    """Add metrics to the graph database.

    Args:
        driver (Driver): Neo4j driver
        metrics (list[dict]): List of metrics for each character
    """
    with driver.session() as session:
        session.run(
            """
    UNWIND $data as row
    MATCH (c:Character{name:row.name})
    SET c.eigen_centrality=toFloat(row.eigen_centrality),
    c.betweenness_centrality=toFloat(row.betweenness_centrality),
    c.degree_centrality=toFloat(row.degree_centrality),
    c.closeness_centrality=toFloat(row.closeness_centrality),
    c.pagerank=toFloat(row.pagerank),
    c.hub=toFloat(row.hub),
    c.authority=toFloat(row.authority),
    c.degree=toInteger(row.degree),
    c.weighted_degree=toInteger(row.weighted_degree),
    c.louvain=toInteger(row.louvain),
    c.leiden=toInteger(row.leiden),
    c.girvan_newman=toInteger(row.girvan_newman),
    c.spectral=toInteger(row.spectral)
    """,
            {"data": metrics},
        )

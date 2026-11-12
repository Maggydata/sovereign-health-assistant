"""Contrôle de fidélité : les faits critiques du scénario sont-ils dans le texte généré ?"""

# Au-delà, le modèle a répété ou divagué (ex. tout le dossier recopié dans chaque rubrique)
RATIO_LONGUEUR_MAX = 2.5


def normaliser(texte: str) -> str:
    """Met en minuscules et supprime tous les espaces (y compris insécables)."""
    return "".join(texte.lower().split())


def faits_manquants(texte: str, faits: list[str]) -> list[str]:
    """Renvoie les faits absents du texte (liste vide = document fidèle)."""
    texte_normalise = normaliser(texte)
    return [fait for fait in faits if normaliser(fait) not in texte_normalise]


def ratio_longueur(texte_genere: str, texte_source: str) -> float:
    """Longueur du texte généré rapportée à celle des faits d'origine (1.0 = même longueur)."""
    return len(texte_genere) / len(texte_source)

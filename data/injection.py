"""Remplacement des balises {{TYPE}} par des valeurs, avec la position de chaque valeur injectée."""

import re

BALISE = re.compile(r"\{\{(\w+)\}\}")  # {{NOM}} → capture "NOM"


def injecter(gabarit: str, valeurs: dict[str, str]) -> tuple[str, list[dict]]:
    """Renvoie le texte final et la liste des entités injectées (type, start, end, valeur)."""
    morceaux = []
    longueur = 0  # longueur du texte final déjà construit
    entites = []
    precedent = 0  # fin de la balise précédente dans le gabarit

    for balise in BALISE.finditer(gabarit):
        type_ = balise.group(1)
        if type_ not in valeurs:
            raise KeyError(f"Balise sans valeur : {{{{{type_}}}}}")
        valeur = valeurs[type_]

        texte_avant = gabarit[precedent:balise.start()]
        morceaux.append(texte_avant)
        longueur += len(texte_avant)

        entites.append({"type": type_, "start": longueur, "end": longueur + len(valeur), "valeur": valeur})
        morceaux.append(valeur)
        longueur += len(valeur)

        precedent = balise.end()

    morceaux.append(gabarit[precedent:])
    return "".join(morceaux), entites

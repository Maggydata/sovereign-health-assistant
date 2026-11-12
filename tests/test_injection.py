from datetime import date

import pytest
from faker import Faker

from data.identites import generer_identite
from data.injection import injecter


def test_exemple_positions_exactes():
    texte, entites = injecter(
        "Patient : {{NOM}}, né le {{DATE_NAISSANCE}}",
        {"NOM": "Marie Dupont", "DATE_NAISSANCE": "12/03/1971"},
    )
    assert texte == "Patient : Marie Dupont, né le 12/03/1971"
    assert entites == [
        {"type": "NOM", "start": 10, "end": 22, "valeur": "Marie Dupont"},
        {"type": "DATE_NAISSANCE", "start": 30, "end": 40, "valeur": "12/03/1971"},
    ]


def test_balise_repetee_donne_deux_entites():
    texte, entites = injecter("{{NOM}} ... revu ce jour, {{NOM}} va mieux.", {"NOM": "Léa Petit"})
    assert [e["start"] for e in entites] == [0, 28]
    assert all(texte[e["start"]:e["end"]] == "Léa Petit" for e in entites)


def test_balise_en_debut_et_en_fin():
    texte, entites = injecter("{{NOM}} et {{NIR}}", {"NOM": "A", "NIR": "1 71 03 69 123 045 39"})
    assert texte == "A et 1 71 03 69 123 045 39"
    assert entites[-1]["end"] == len(texte)


def test_texte_sans_balise_inchange():
    assert injecter("Aucune balise ici.", {}) == ("Aucune balise ici.", [])


def test_balise_inconnue_leve_une_erreur():
    with pytest.raises(KeyError, match="PRENOM"):
        injecter("Bonjour {{PRENOM}}", {"NOM": "Marie Dupont"})


def test_entete_realiste_positions_justes():
    faker = Faker("fr_FR")
    faker.seed_instance(42)
    valeurs = generer_identite("F", 67, date(2026, 3, 14), faker) | {"DATE_CONSULTATION": "14/03/2026"}
    gabarit = (
        "COMPTE RENDU DE CONSULTATION — {{DATE_CONSULTATION}}\n"
        "Patiente : {{NOM}}, née le {{DATE_NAISSANCE}}\n"
        "Adresse : {{ADRESSE}} — Tél. : {{TELEPHONE}}\n"
        "NIR : {{NIR}}\n"
        "Médecin : Dr {{MEDECIN}}"
    )
    texte, entites = injecter(gabarit, valeurs)
    assert "{{" not in texte
    assert len(entites) == 7
    for e in entites:
        assert texte[e["start"]:e["end"]] == e["valeur"]

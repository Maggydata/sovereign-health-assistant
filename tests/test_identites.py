from datetime import date, datetime

import pytest
from faker import Faker

from data.identites import cle_nir, construire_nir, generer_identite, retirer_annees, tirer_date_naissance

REFERENCE = date(2026, 3, 14)


@pytest.fixture
def faker():
    f = Faker("fr_FR")
    f.seed_instance(42)
    return f


def age_a(naissance: date, reference: date) -> int:
    return reference.year - naissance.year - ((reference.month, reference.day) < (naissance.month, naissance.day))


def test_cle_nir_exemple_connu():
    assert cle_nir("1710369123045") == "39"


def test_cle_nir_toujours_sur_deux_chiffres():
    # 97 - 90 = 7 → doit donner "07"
    numero = next(n for n in range(10**12, 10**12 + 200) if n % 97 == 90)
    assert cle_nir(str(numero)) == "07"


def test_retirer_annees_29_fevrier():
    assert retirer_annees(date(2024, 2, 29), 1) == date(2023, 2, 28)


def test_date_naissance_donne_l_age_exact(faker):
    for _ in range(200):
        naissance = tirer_date_naissance(54, REFERENCE, faker)
        assert age_a(naissance, REFERENCE) == 54


def test_nir_coherent_avec_sexe_et_naissance(faker):
    naissance = date(1971, 3, 12)
    nir = construire_nir("F", naissance, faker)
    chiffres = nir.replace(" ", "")
    assert len(chiffres) == 15
    assert chiffres[0] == "2"  # femme
    assert chiffres[1:3] == "71"
    assert chiffres[3:5] == "03"
    assert chiffres[5:7] != "20"  # Corse exclue


def test_nir_cle_valide(faker):
    for _ in range(100):
        chiffres = construire_nir("M", date(1980, 7, 1), faker).replace(" ", "")
        assert (int(chiffres[:13]) + int(chiffres[13:])) % 97 == 0


def test_identite_complete_et_coherente(faker):
    identite = generer_identite("M", 54, REFERENCE, faker)
    assert set(identite) == {"NOM", "DATE_NAISSANCE", "ADRESSE", "TELEPHONE", "NIR", "MEDECIN"}
    assert "\n" not in identite["ADRESSE"]
    naissance = datetime.strptime(identite["DATE_NAISSANCE"], "%d/%m/%Y").date()
    assert age_a(naissance, REFERENCE) == 54
    assert identite["NIR"].startswith("1")


def test_meme_graine_meme_identite():
    identites = []
    for _ in range(2):
        f = Faker("fr_FR")
        f.seed_instance(42)
        identites.append(generer_identite("F", 29, REFERENCE, f))
    assert identites[0] == identites[1]

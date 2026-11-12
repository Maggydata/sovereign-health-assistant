from data.generate import (
    ESSAIS_MAX,
    Rubriques,
    assembler_corps,
    construire_entete,
    construire_prompt,
    generer_document,
)
from data.fidelite import RATIO_LONGUEUR_MAX
from src.llm.client import Mesures

DOCUMENT = {
    "rubriques": {
        "motif": "douleurs thoraciques",
        "antecedents": "aucun",
        "examen_clinique": "normal",
        "examens_complementaires": "ECG normal",
        "conclusion": "angor probable",
        "traitement": "aspirine 75 mg",
    },
    "faits_critiques": ["aspirine", "75 mg"],
}

VALEURS = {
    "DATE_CONSULTATION": "14/03/2026",
    "NOM": "Marie Dupont",
    "DATE_NAISSANCE": "12/03/1971",
    "ADRESSE": "8 rue des Lilas, 69003 Lyon",
    "TELEPHONE": "06 12 34 56 78",
    "NIR": "2 71 03 69 123 045 39",
    "MEDECIN": "Paul Martin",
}

FIDELE = Rubriques(
    motif="Douleurs thoraciques.",
    antecedents="Aucun.",
    examen_clinique="Normal.",
    examens_complementaires="ECG normal.",
    conclusion="Angor probable.",
    traitement="Aspirine 75 mg par jour.",
)
INFIDELE = FIDELE.model_copy(update={"traitement": "Aspirine par jour."})  # dose oubliée
BAVARD = FIDELE.model_copy(update={"motif": "Douleurs thoraciques. " * 10})  # tous les faits, mais répétés

MESURE = Mesures(modele="faux", duree_totale_s=1.0, tokens_prompt=10, tokens_generes=20, tokens_par_s=20.0)


class FauxModele:
    """Remplace le vrai LLM : renvoie les réponses prévues, dans l'ordre, et compte les appels."""

    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = 0
        self.graines = []

    def __call__(self, prompt, schema, modele, graine):
        self.appels += 1
        self.graines.append(graine)
        return self.reponses.pop(0), MESURE


def test_prompt_contient_les_faits():
    prompt = construire_prompt(DOCUMENT["rubriques"], "M", 54)
    assert "motif : douleurs thoraciques" in prompt
    assert "traitement : aspirine 75 mg" in prompt


def test_prompt_precise_sexe_et_age():
    assert "un homme de 54 ans" in construire_prompt(DOCUMENT["rubriques"], "M", 54)
    prompt_femme = construire_prompt(DOCUMENT["rubriques"], "F", 67)
    assert "une femme de 67 ans" in prompt_femme
    assert "féminin" in prompt_femme


def test_corps_avec_titres_dans_l_ordre():
    lignes = assembler_corps(FIDELE).split("\n")
    assert len(lignes) == 6
    assert lignes[0] == "Motif : Douleurs thoraciques."
    assert lignes[-1] == "Traitement : Aspirine 75 mg par jour."


def test_entete_accorde_au_sexe():
    assert "Patiente : {{NOM}}, née le" in construire_entete("F")
    assert "Patient : {{NOM}}, né le" in construire_entete("M")


def test_document_fidele_accepte_au_premier_essai():
    faux = FauxModele([FIDELE])
    resultat = generer_document(DOCUMENT, "F", 57, VALEURS, appeler_llm=faux)
    assert faux.appels == 1
    assert resultat.essais == 1
    assert resultat.manquants == []
    assert len(resultat.entites) == 7
    for e in resultat.entites:
        assert resultat.texte[e["start"]:e["end"]] == e["valeur"]
    assert resultat.texte.endswith(assembler_corps(FIDELE))


def test_document_infidele_puis_fidele_reessaie():
    faux = FauxModele([INFIDELE, FIDELE])
    resultat = generer_document(DOCUMENT, "F", 57, VALEURS, appeler_llm=faux)
    assert faux.appels == 2
    assert resultat.essais == 2
    assert resultat.texte is not None
    assert len(resultat.mesures) == 2
    assert resultat.manquants_par_essai == [["75 mg"], []]


def test_document_toujours_infidele_abandonne():
    faux = FauxModele([INFIDELE] * ESSAIS_MAX)
    resultat = generer_document(DOCUMENT, "F", 57, VALEURS, appeler_llm=faux)
    assert faux.appels == ESSAIS_MAX
    assert resultat.texte is None
    assert resultat.entites == []
    assert resultat.manquants == ["75 mg"]
    assert resultat.manquants_par_essai == [["75 mg"]] * ESSAIS_MAX


def test_document_trop_long_reessaie():
    faux = FauxModele([BAVARD, FIDELE])
    resultat = generer_document(DOCUMENT, "F", 57, VALEURS, appeler_llm=faux)
    assert faux.appels == 2
    assert resultat.texte is not None
    assert resultat.manquants_par_essai == [[], []]  # aucun fait manquant…
    assert resultat.ratios_par_essai[0] > RATIO_LONGUEUR_MAX  # …mais le 1er essai était trop long
    assert resultat.ratios_par_essai[1] <= RATIO_LONGUEUR_MAX


def test_graine_differente_a_chaque_essai():
    faux = FauxModele([INFIDELE, INFIDELE, FIDELE])
    generer_document(DOCUMENT, "F", 57, VALEURS, graine=100, appeler_llm=faux)
    assert faux.graines == [101, 102, 103]


def test_reponse_invalide_reessaie():
    faux = FauxModele([None, FIDELE])  # None = JSON coupé par max_tokens
    resultat = generer_document(DOCUMENT, "F", 57, VALEURS, appeler_llm=faux)
    assert faux.appels == 2
    assert resultat.texte is not None
    assert resultat.manquants_par_essai[0] == ["(réponse invalide)"]
    assert resultat.ratios_par_essai[0] is None


def test_reponses_toujours_invalides_abandonne():
    faux = FauxModele([None] * ESSAIS_MAX)
    resultat = generer_document(DOCUMENT, "F", 57, VALEURS, appeler_llm=faux)
    assert resultat.texte is None
    assert resultat.manquants == ["(réponse invalide)"]

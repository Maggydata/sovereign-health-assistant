from data.fidelite import faits_manquants, normaliser, ratio_longueur


def test_normaliser_minuscules_et_espaces():
    assert normaliser("HbA1c 8,4 %") == "hba1c8,4%"


def test_tous_les_faits_presents():
    texte = "Aspirine 75 mg et bisoprolol 2,5 mg."
    assert faits_manquants(texte, ["aspirine", "75 mg", "bisoprolol"]) == []


def test_fait_absent_est_renvoye():
    texte = "Fumeur de 30 cigarettes par jour."
    assert faits_manquants(texte, ["paquets-années"]) == ["paquets-années"]


def test_espace_avant_pourcentage_ignore():
    assert faits_manquants("HbA1c à 8,4%", ["8,4 %"]) == []


def test_majuscules_ignorees():
    assert faits_manquants("ASPIRINE 75 MG", ["aspirine 75 mg"]) == []


def test_espace_insecable_ignore():
    assert faits_manquants("aspirine 75 mg", ["75 mg"]) == []


def test_seuls_les_faits_manquants_sont_renvoyes():
    texte = "Aspirine 75 mg ; bisoprolol."
    assert faits_manquants(texte, ["aspirine", "trinitrine", "bisoprolol"]) == ["trinitrine"]


def test_ratio_longueur():
    assert ratio_longueur("a" * 30, "a" * 10) == 3.0
    assert ratio_longueur("a" * 10, "a" * 10) == 1.0

from types import SimpleNamespace

import pytest
from ollama import Client
from pydantic import BaseModel

from src.llm.client import extraire_mesures, generer_structure


def ollama_disponible() -> bool:
    try:
        Client().list()
        return True
    except Exception:
        return False


def test_extraire_mesures_convertit_les_nanosecondes():
    reponse = SimpleNamespace(
        model="qwen2.5:3b",
        total_duration=10_000_000_000,  # 10 s
        prompt_eval_count=100,
        eval_count=250,
        eval_duration=5_000_000_000,  # 5 s
    )
    mesures = extraire_mesures(reponse)
    assert mesures.duree_totale_s == 10
    assert mesures.tokens_generes == 250
    assert mesures.tokens_par_s == 50


def test_extraire_mesures_prompt_en_cache():
    reponse = SimpleNamespace(
        model="qwen2.5:3b",
        total_duration=1,
        prompt_eval_count=None,
        eval_count=1,
        eval_duration=1,
    )
    assert extraire_mesures(reponse).tokens_prompt == 0


class Capitale(BaseModel):
    ville: str


class FauxClient:
    """Remplace le client Ollama : renvoie une réponse fixée et garde les arguments reçus."""

    def __init__(self, texte_reponse: str):
        self.texte_reponse = texte_reponse
        self.arguments = None

    def generate(self, **arguments):
        self.arguments = arguments
        return SimpleNamespace(
            model="faux",
            response=self.texte_reponse,
            total_duration=1,
            prompt_eval_count=1,
            eval_count=5,
            eval_duration=1,
        )


def test_graine_et_max_tokens_transmis():
    faux = FauxClient('{"ville": "Paris"}')
    sortie, _ = generer_structure("?", Capitale, graine=7, max_tokens=100, client=faux)
    assert faux.arguments["options"] == {"num_predict": 100, "seed": 7}
    assert sortie.ville == "Paris"


def test_sans_graine_pas_de_seed():
    faux = FauxClient('{"ville": "Paris"}')
    generer_structure("?", Capitale, client=faux)
    assert "seed" not in faux.arguments["options"]


def test_reponse_tronquee_donne_none_avec_mesures():
    faux = FauxClient('{"ville": "Par')  # JSON coupé par max_tokens
    sortie, mesures = generer_structure("?", Capitale, client=faux)
    assert sortie is None
    assert mesures.tokens_generes == 5


@pytest.mark.ollama
@pytest.mark.skipif(not ollama_disponible(), reason="serveur Ollama arrêté")
def test_generer_structure_avec_le_vrai_modele():
    sortie, mesures = generer_structure("Quelle est la capitale de la France ?", Capitale)
    assert "paris" in sortie.ville.lower()
    assert mesures.tokens_generes > 0

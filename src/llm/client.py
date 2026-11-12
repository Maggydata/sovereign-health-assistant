"""Client Ollama : appel d'un modèle local avec sortie structurée et mesures."""

from dataclasses import dataclass

from ollama import Client
from pydantic import BaseModel, ValidationError

MODELE_PAR_DEFAUT = "qwen2.5:3b"
MAX_TOKENS_PAR_DEFAUT = 700  # coupe les emballements (réponses normales : 150 à 500 tokens)
NS_PAR_SECONDE = 1e9  # Ollama renvoie ses durées en nanosecondes


@dataclass
class Mesures:
    modele: str
    duree_totale_s: float
    tokens_prompt: int
    tokens_generes: int
    tokens_par_s: float


def extraire_mesures(reponse) -> Mesures:
    """Convertit les compteurs bruts d'Ollama en mesures lisibles."""
    return Mesures(
        modele=reponse.model,
        duree_totale_s=reponse.total_duration / NS_PAR_SECONDE,
        tokens_prompt=reponse.prompt_eval_count or 0,  # None si le prompt était en cache
        tokens_generes=reponse.eval_count,
        tokens_par_s=reponse.eval_count / (reponse.eval_duration / NS_PAR_SECONDE),
    )


def generer_structure(
    prompt: str,
    schema: type[BaseModel],
    modele: str = MODELE_PAR_DEFAUT,
    graine: int | None = None,
    max_tokens: int = MAX_TOKENS_PAR_DEFAUT,
    client: Client | None = None,
) -> tuple[BaseModel | None, Mesures]:
    """Demande au modèle une réponse conforme au schéma Pydantic, puis la valide.

    La sortie vaut None si la réponse ne respecte pas le schéma (par exemple coupée
    par max_tokens) ; les mesures sont renvoyées dans tous les cas.
    """
    client = client or Client()
    options = {"num_predict": max_tokens}
    if graine is not None:
        options["seed"] = graine  # même graine + même prompt = même texte
    reponse = client.generate(
        model=modele,
        prompt=prompt,
        format=schema.model_json_schema(),  # Ollama contraint la génération à ce schéma
        options=options,
    )
    try:
        sortie = schema.model_validate_json(reponse.response)
    except ValidationError:
        sortie = None
    return sortie, extraire_mesures(reponse)

"""Génération des comptes rendus fictifs : scénario → LLM → contrôle de fidélité → injection."""

import argparse
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from faker import Faker
from pydantic import BaseModel

from data.fidelite import RATIO_LONGUEUR_MAX, faits_manquants, ratio_longueur
from data.identites import generer_identite
from data.injection import injecter
from src.llm.client import MODELE_PAR_DEFAUT, Mesures, generer_structure

ESSAIS_MAX = 3

DOSSIER = Path(__file__).parent
SCENARIOS = DOSSIER / "scenarios.json"
DOCUMENTS = DOSSIER / "documents"
GROUND_TRUTH = DOSSIER / "ground_truth.json"

TITRES = {
    "motif": "Motif",
    "antecedents": "Antécédents",
    "examen_clinique": "Examen clinique",
    "examens_complementaires": "Examens complémentaires",
    "conclusion": "Conclusion",
    "traitement": "Traitement",
}


class Rubriques(BaseModel):
    motif: str
    antecedents: str
    examen_clinique: str
    examens_complementaires: str
    conclusion: str
    traitement: str


@dataclass
class ResultatDocument:
    texte: str | None  # None si le document a été abandonné
    entites: list[dict]
    essais: int
    manquants: list[str]  # faits manquants au dernier essai
    mesures: list[Mesures] = field(default_factory=list)
    manquants_par_essai: list[list[str]] = field(default_factory=list)  # [] pour un essai réussi
    ratios_par_essai: list[float | None] = field(default_factory=list)  # None si réponse invalide


def construire_prompt(rubriques: dict[str, str], sexe: str, age: int) -> str:
    faits = "\n".join(f"{cle} : {valeur}" for cle, valeur in rubriques.items())
    if sexe == "M":
        personne = f"Le patient est un homme de {age} ans."
    else:
        personne = f"La patiente est une femme de {age} ans : accorde au féminin (« la patiente »)."
    return (
        "Tu es un médecin généraliste français. Reformule chaque rubrique en une ou deux phrases "
        "de style compte rendu médical, en français correct. Garde TOUS les faits de la rubrique, "
        "n'en ajoute aucun, ne déplace rien d'une rubrique à l'autre.\n"
        + personne + "\n\n" + faits
    )


def assembler_corps(rubriques: Rubriques) -> str:
    return "\n".join(f"{TITRES[cle]} : {texte.strip()}" for cle, texte in rubriques.model_dump().items())


def construire_entete(sexe: str) -> str:
    patient, ne = ("Patient", "né") if sexe == "M" else ("Patiente", "née")
    return (
        "COMPTE RENDU DE CONSULTATION — {{DATE_CONSULTATION}}\n"
        + patient + " : {{NOM}}, " + ne + " le {{DATE_NAISSANCE}}\n"
        "Adresse : {{ADRESSE}} — Tél. : {{TELEPHONE}}\n"
        "NIR : {{NIR}}\n"
        "Médecin : Dr {{MEDECIN}}"
    )


def generer_document(
    document: dict,
    sexe: str,
    age: int,
    valeurs: dict[str, str],
    modele: str = MODELE_PAR_DEFAUT,
    graine: int = 0,
    appeler_llm=generer_structure,  # remplaçable par un faux modèle dans les tests
) -> ResultatDocument:
    """Fait rédiger le corps par le LLM (jusqu'à ESSAIS_MAX fois), puis ajoute l'en-tête injecté.

    L'essai n utilise la graine `graine + n` : reproductible, mais différente à chaque essai.
    """
    prompt = construire_prompt(document["rubriques"], sexe, age)
    source = " ".join(document["rubriques"].values())
    mesures = []
    manquants_par_essai = []
    ratios_par_essai = []

    for essai in range(1, ESSAIS_MAX + 1):
        sortie, mesure = appeler_llm(prompt, Rubriques, modele=modele, graine=graine + essai)
        mesures.append(mesure)
        if sortie is None:  # JSON invalide, par exemple coupé par max_tokens
            manquants = ["(réponse invalide)"]
            manquants_par_essai.append(manquants)
            ratios_par_essai.append(None)
            continue
        corps = assembler_corps(sortie)
        manquants = faits_manquants(corps, document["faits_critiques"])
        ratio = ratio_longueur(" ".join(sortie.model_dump().values()), source)  # sans les titres
        manquants_par_essai.append(manquants)
        ratios_par_essai.append(round(ratio, 2))
        if not manquants and ratio <= RATIO_LONGUEUR_MAX:
            # L'en-tête est injecté seul, puis le corps est ajouté après :
            # les positions de l'en-tête restent donc valables dans le texte final.
            entete, entites = injecter(construire_entete(sexe), valeurs)
            return ResultatDocument(
                entete + "\n\n" + corps, entites, essai, [], mesures, manquants_par_essai, ratios_par_essai
            )

    return ResultatDocument(None, [], ESSAIS_MAX, manquants, mesures, manquants_par_essai, ratios_par_essai)


def resumer_mesures(nom: str, resultat: ResultatDocument, modele: str) -> dict:
    """Une ligne du rapport : additionne les mesures de tous les essais du document."""
    mesures = resultat.mesures
    return {
        "document": nom,
        "modele": modele,
        "essais": resultat.essais,
        "abandonne": resultat.texte is None,
        "manquants": resultat.manquants,
        "manquants_par_essai": resultat.manquants_par_essai,
        "ratios_par_essai": resultat.ratios_par_essai,
        "duree_totale_s": round(sum(m.duree_totale_s for m in mesures), 2),
        "tokens_generes": sum(m.tokens_generes for m in mesures),
        "tokens_par_s": round(sum(m.tokens_par_s for m in mesures) / len(mesures), 1),
    }


def main():
    parser = argparse.ArgumentParser(description="Génère les comptes rendus fictifs.")
    parser.add_argument("--modele", default=MODELE_PAR_DEFAUT)
    parser.add_argument("--limite", type=int, default=None, help="nombre maximum de documents")
    parser.add_argument("--graine", type=int, default=42)
    args = parser.parse_args()

    faker = Faker("fr_FR")
    faker.seed_instance(args.graine)
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))

    # Supprime les anciens documents pour rester cohérent avec le nouveau ground_truth.json
    DOCUMENTS.mkdir(exist_ok=True)
    anciens = list(DOCUMENTS.glob("*.txt"))
    for fichier in anciens:
        fichier.unlink()
    if anciens:
        print(f"{len(anciens)} anciens documents supprimés")

    ground_truth = []
    rapport = []
    for patient in scenarios:
        premiere = faker.date_between_dates(date(2025, 1, 1), date(2026, 6, 30))
        identite = generer_identite(patient["sexe"], patient["age"], premiere, faker)

        for numero, document in enumerate(patient["documents"], start=1):
            if args.limite is not None and len(rapport) >= args.limite:
                break
            nom = f"{patient['id']}_{numero:02d}.txt"
            consultation = premiere + timedelta(days=document["jour"])
            valeurs = identite | {"DATE_CONSULTATION": consultation.strftime("%d/%m/%Y")}

            # Graine propre à chaque document ; les essais y ajoutent 1, 2, 3
            graine_document = args.graine * 1000 + len(rapport) * 10
            resultat = generer_document(
                document, patient["sexe"], patient["age"], valeurs, modele=args.modele, graine=graine_document
            )
            ligne = resumer_mesures(nom, resultat, args.modele)
            rapport.append(ligne)

            if resultat.texte is None:
                print(
                    f"{nom}  ✗ abandonné après {resultat.essais} essais, "
                    f"manquants : {resultat.manquants}, ratios : {resultat.ratios_par_essai}"
                )
                continue
            (DOCUMENTS / nom).write_text(resultat.texte, encoding="utf-8")
            ground_truth += [{"document": nom, **entite} for entite in resultat.entites]
            print(f"{nom}  ✓ {resultat.essais} essai(s)  {ligne['duree_totale_s']} s  {ligne['tokens_par_s']} tok/s")

    if not rapport:
        print("Aucun document généré.")
        return

    acceptes = [ligne for ligne in rapport if not ligne["abandonne"]]
    resume = {
        "modele": args.modele,
        "graine": args.graine,
        "documents": len(rapport),
        "acceptes": len(acceptes),
        "abandons": len(rapport) - len(acceptes),
        "reussite_premier_essai": round(sum(ligne["essais"] == 1 for ligne in acceptes) / len(rapport), 2),
        "essais_total": sum(ligne["essais"] for ligne in rapport),
        "duree_totale_s": round(sum(ligne["duree_totale_s"] for ligne in rapport), 1),
        "entites": len(ground_truth),
    }

    GROUND_TRUTH.write_text(json.dumps(ground_truth, ensure_ascii=False, indent=2), encoding="utf-8")
    chemin_rapport = DOSSIER / f"rapport_generation_{args.modele.replace(':', '-')}.json"
    chemin_rapport.write_text(
        json.dumps({"resume": resume, "documents": rapport}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(resume, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

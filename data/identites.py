"""Identités fictives cohérentes (sexe, âge, NIR) générées avec Faker."""

from datetime import date, timedelta

from faker import Faker


def cle_nir(treize_chiffres: str) -> str:
    """Clé de contrôle du NIR : 97 - (numéro modulo 97), sur 2 chiffres."""
    return f"{97 - int(treize_chiffres) % 97:02d}"


def retirer_annees(d: date, annees: int) -> date:
    """Recule une date de n années (un 29 février devient un 28 février)."""
    try:
        return d.replace(year=d.year - annees)
    except ValueError:
        return d.replace(year=d.year - annees, day=28)


def tirer_date_naissance(age: int, date_reference: date, faker: Faker) -> date:
    """Date de naissance telle que le patient a exactement `age` ans à `date_reference`."""
    plus_tot = retirer_annees(date_reference, age + 1) + timedelta(days=1)
    plus_tard = retirer_annees(date_reference, age)
    return faker.date_between_dates(plus_tot, plus_tard)


def construire_nir(sexe: str, naissance: date, faker: Faker) -> str:
    """NIR fictif cohérent avec le sexe et la date de naissance (Corse exclue)."""
    departement = faker.random_element([n for n in range(1, 96) if n != 20])
    treize = (
        ("1" if sexe == "M" else "2")
        + f"{naissance.year % 100:02d}"
        + f"{naissance.month:02d}"
        + f"{departement:02d}"
        + f"{faker.random_int(1, 999):03d}"  # commune
        + f"{faker.random_int(1, 999):03d}"  # numéro d'ordre
    )
    # Format usuel : 1 71 03 69 123 045 39
    return f"{treize[0]} {treize[1:3]} {treize[3:5]} {treize[5:7]} {treize[7:10]} {treize[10:]} {cle_nir(treize)}"


def generer_identite(sexe: str, age: int, date_reference: date, faker: Faker) -> dict[str, str]:
    """Identité complète d'un patient, clés = noms des balises de l'en-tête."""
    prenom = faker.first_name_male() if sexe == "M" else faker.first_name_female()
    naissance = tirer_date_naissance(age, date_reference, faker)
    return {
        "NOM": f"{prenom} {faker.last_name()}",
        "DATE_NAISSANCE": naissance.strftime("%d/%m/%Y"),
        "ADRESSE": faker.address().replace("\n", ", "),
        "TELEPHONE": faker.phone_number(),
        "NIR": construire_nir(sexe, naissance, faker),
        "MEDECIN": f"{faker.first_name()} {faker.last_name()}",
    }

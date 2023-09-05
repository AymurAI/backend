import re
import locale
from datetime import datetime

import pandas as pd
from faker import Faker
from faker.providers import BaseProvider
from numpy.random import choice, randint
from faker.providers.person.es_AR import Provider

from aymurai.utils.json_data import load_json

locale.setlocale(locale.LC_TIME, "es_AR.UTF-8")


with open("/resources/data-augmentation/bank_codes.list", "r") as file:
    bank_codes = file.read().splitlines()

with open("/resources/data-augmentation/nationalities.list", "r") as file:
    nationalities = file.read().splitlines()

cars = load_json("/resources/data-augmentation/cars.json")
localidades = pd.read_csv("/resources/data-augmentation/localidades.csv")


class CarProvider(BaseProvider):
    def plate(self) -> str:
        license_plate = faker.license_plate()
        len_license_plate = len(license_plate)

        spaced = choice([0, 1], p=[0.75, 0.25])
        if spaced:
            if len_license_plate > 6:
                license_plate = (
                    license_plate[:2]
                    + " "
                    + license_plate[2:5]
                    + " "
                    + license_plate[5:]
                )  # noqa
            else:
                license_plate = license_plate[:3] + " " + license_plate[3:]

        return license_plate

    def car_model(self) -> str:
        brand = choice(list(cars.keys()))
        model = choice(cars.get(brand))
        brand_model = f"{brand} {model}"

        named = choice([0, 1])
        if named:
            brand_model = f"{brand} modelo {model}"

        return brand_model


class DatePlaceProvider(BaseProvider):
    def formatted_date(self) -> str:
        formats = [
            "%A %d de %B del %Y",
            "%d de %B del %Y",
            "%d de %B de %Y",
            "%d de %B del '%y",
            "%d-%m-%y",
            "%d-%m-%Y",
            "%d/%m/%y",
            "%d/%m/%Y",
        ]
        dt = datetime.strptime(faker.date(), "%Y-%m-%d")
        return dt.strftime(choice(formats))

    def direction(self) -> str:
        formats = ["address", "intersection", "street"]
        fmt = choice(formats, p=[0.6, 0.3, 0.1])

        if fmt == "street":
            return faker.street_name()

        elif fmt == "intersection":
            return f"{faker.street_name()} y {faker.street_name()}"

        return re.sub(r"\n.+$", "", faker.address())

    def location(self) -> str:
        sample = localidades.sample().dropna().values[0]
        levels = randint(1, 4)

        if levels == 1:
            return sample[0]

        if levels == 2:
            return ", ".join(sample[0:2])

        return ", ".join(sample)


class JudicialProvider(BaseProvider):
    def exp(self) -> str:
        prefix = choice(["IPP", "CAU", "DEB", "INC"])
        one_digit = str(randint(0, 10))
        year = str(randint(1990, 2100))
        three_six_digits = "".join(
            randint(0, 10, size=choice(list(range(3, 7)))).astype(str)
        )  # noqa
        return f"{prefix} {three_six_digits}/{year}-{one_digit}"

    def cuij(self) -> str:
        prefix = choice(["IPP", "CAU", "DEB", "INC"])
        one_digit = str(randint(0, 10))
        two_digits = "".join(randint(0, 10, size=2).astype(str))
        eight_digits = "".join(randint(0, 10, size=8).astype(str))
        year = str(randint(1990, 2100))
        return f"{prefix} J-{two_digits}-{eight_digits}-{one_digit}/{year}-{one_digit}"

    def act(self) -> str:
        year = str(randint(1990, 2100))
        two_seven_digits = "".join(
            randint(0, 10, size=choice(list(range(2, 8)))).astype(str)
        )  # noqa
        return f"{two_seven_digits}/{year}"


class NumberProvider(BaseProvider):
    def _insert_dots_or_spaces(self, register: str, fmt: str) -> str:
        reversed_register = register[::-1]

        if fmt == "spaced":
            reversed_register = reversed_register[:3] + " " + reversed_register[3:]
        else:
            reversed_register = reversed_register[:3] + "." + reversed_register[3:]

        register = reversed_register[::-1]
        return register

    def cuit_cuil(self) -> str:
        prefix = choice([20, 23, 24, 25, 26, 27, 30])
        eight_digits = "".join(randint(0, 10, size=8).astype(str))
        suffix = randint(0, 10)
        return f"{prefix}-{eight_digits}-{suffix}"

    def cbu(self) -> str:
        bank_code = choice(bank_codes)
        nineteen_digits = "".join(randint(0, 10, size=19).astype(str))
        return f"{bank_code}{nineteen_digits}"

    def phone(self) -> str:
        phone_number = faker.phone_number()

        remove_prefix = choice([0, 1], p=[0.05, 0.95])
        if remove_prefix:
            phone_number = re.sub(r"\+54 (?:9 )?", "", phone_number)

        formats = ["numeric", "dashed", "spaced"]
        fmt = choice(formats, p=[0.4, 0.4, 0.2])

        if fmt == "numeric":
            return re.sub(r"\s+", "", phone_number)

        if fmt == "dashed":
            return re.sub(r"\s+", "-", phone_number)

        return phone_number

    def register(self) -> str:
        n_digits = choice([5, 6])
        digits = "".join(randint(0, 10, size=n_digits).astype(str))

        formats = ["dotted", "numeric", "spaced"]
        fmt = choice(formats, p=[0.7, 0.2, 0.1])

        if fmt in ("dotted", "spaced"):
            digits = self._insert_dots_or_spaces(digits, fmt)

        return digits

    def savings_account(self) -> str:
        prefix = "".join(randint(0, 10, size=2).astype(str))
        account_type = choice(["0200", "0210"])
        nine_digits = "".join(randint(0, 10, size=9).astype(str))
        three_digits = "".join(randint(0, 10, size=3).astype(str))
        return f"{prefix}{account_type}{nine_digits}{three_digits}"


class PersonProvider(Provider):
    def _insert_dots_or_spaces(self, dni: str, fmt: str) -> str:
        reversed_dni = dni[::-1]

        if fmt == "spaced":
            reversed_dni = (
                reversed_dni[:3] + " " + reversed_dni[3:6] + " " + reversed_dni[6:]
            )  # noqa
        else:
            reversed_dni = (
                reversed_dni[:3] + "." + reversed_dni[3:6] + "." + reversed_dni[6:]
            )  # noqa

        dni = reversed_dni[::-1]
        return dni

    def name(self) -> str:
        n_last_names = randint(1, 4)
        last_names = " ".join([faker.last_name() for i in range(n_last_names)])

        name = f"{faker.first_name_nonbinary()} {last_names}"

        initials = choice([0, 1], p=[0.75, 0.25])
        if initials:
            name = "".join(x[0].upper() + "." for x in name.split(" "))
            spaced = choice([0, 1], p=[0.75, 0.25])
            if spaced:
                name = ". ".join(name.split(".")).strip()

        return name

    def age(self) -> str:
        years = choice([0, 1], p=[0.2, 0.8])

        if not years:
            months = randint(1, 12)
            return f"{months} meses" if months > 1 else f"{months} mes"

        return str(randint(1, 100))

    def dni(self) -> str:
        dni = str(randint(low=1_000_000, high=100_000_000))

        formats = ["dotted", "numeric", "spaced"]
        fmt = choice(formats, p=[0.7, 0.2, 0.1])

        if fmt in ("dotted", "spaced"):
            dni = self._insert_dots_or_spaces(dni, fmt)
        return dni

    def nationality(self) -> str:
        return choice(nationalities)

    def studies(self) -> str:
        levels = ["primarios", "secundarios", "terciarios", "universitarios"]
        status = ["completos", "incompletos", "en curso"]
        return f"estudios {choice(levels)} {choice(status)}"


faker = Faker(locale="es_AR")
faker.add_provider(CarProvider)
faker.add_provider(DatePlaceProvider)
faker.add_provider(JudicialProvider)
faker.add_provider(NumberProvider)
faker.add_provider(PersonProvider)


augmentation_functions = {
    "PER": faker.name,
    "EDAD": faker.age,
    "DNI": faker.dni,
    "NACIONALIDAD": faker.nationality,
    "ESTUDIOS": faker.studies,
    "PASAPORTE": faker.passport_number,
    "NUM_MATRICULA": faker.register,
    "DIRECCION": faker.direction,
    "LOC": faker.location,
    "FECHA": faker.formatted_date,
    "NUM_EXPEDIENTE": faker.exp,
    "CUIJ": faker.cuij,
    "NUM_ACTUACION": faker.act,
    "CORREO_ELECTRONICO": faker.ascii_email,
    "USUARIX": faker.user_name,
    "LINK": faker.url,
    "NOMBRE_ARCHIVO": faker.file_name,
    "IP": faker.ipv4,
    "CUIT_CUIL": faker.cuit_cuil,
    "TELEFONO": faker.phone,
    "BANCO": faker.bank,
    "CBU": faker.cbu,
    "NUM_CAJA_AHORRO": faker.savings_account,
    "MARCA_AUTOMOVIL": faker.car_model,
    "PATENTE_DOMINIO": faker.plate,
}

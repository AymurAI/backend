import re
import locale
from datetime import datetime
from collections import OrderedDict

import pandas as pd
from faker import Faker
from faker.providers import BaseProvider
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
    def random_bool(self, p: float = 0.5) -> bool:
        return self.random_element(OrderedDict([(True, p), (False, 1 - p)]))

    def plate(self) -> str:
        license_plate = faker.license_plate()
        len_license_plate = len(license_plate)

        spaced = self.random_bool(p=0.25)
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
        brand = self.random_element(list(cars.keys()))
        model = self.random_element(cars.get(brand))
        brand_model = f"{brand} {model}"

        named = self.random_bool(p=0.5)
        if named:
            brand_model = f"{brand} modelo {model}"

        return brand_model


class DatePlaceProvider(BaseProvider):
    def random_bool(self, p: float = 0.5) -> bool:
        return self.random_element(OrderedDict([(True, p), (False, 1 - p)]))

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
        fmt = self.random_element(formats)
        return dt.strftime(fmt)

    def direction(self) -> str:
        fmt = self.random_element(
            OrderedDict([["address", 0.6], ["intersection", 0.3], ["street", 0.1]])
        )

        if fmt == "street":
            return faker.street_name()

        elif fmt == "intersection":
            return f"{faker.street_name()} y {faker.street_name()}"

        return re.sub(r"\n.+$", "", faker.address())

    def location(self) -> str:
        sample = self.random_element(localidades.values)
        sample = [element for element in sample if not pd.isna(element)]
        levels = self.random_int(1, 4)

        if levels == 1:
            return sample[0]

        if levels == 2:
            return ", ".join(sample[0:2])

        return ", ".join(sample)


class JudicialProvider(BaseProvider):
    def random_bool(self, p: float = 0.5) -> bool:
        return self.random_element(OrderedDict([(True, p), (False, 1 - p)]))

    def exp(self) -> str:
        prefix = self.random_element(["IPP", "CAU", "DEB", "INC"])
        one_digit = str(self.random_digit())
        year = str(self.random_int(min=1990, max=2100))

        size = self.random_int(3, 7)
        three_six_digits = [str(self.random_digit()) for _ in range(size)]
        three_six_digits = "".join(three_six_digits)

        return f"{prefix} {three_six_digits}/{year}-{one_digit}"

    def cuij(self) -> str:
        prefix = self.random_element(["IPP", "CAU", "DEB", "INC"])

        one_digit = str(self.random_digit())

        two_digits = [str(self.random_digit()) for _ in range(2)]
        two_digits = "".join(two_digits)

        eight_digits = [str(self.random_digit()) for _ in range(8)]
        eight_digits = "".join(eight_digits)

        year = str(self.random_int(min=1990, max=2100))
        return f"{prefix} J-{two_digits}-{eight_digits}-{one_digit}/{year}-{one_digit}"

    def act(self) -> str:
        year = str(self.random_int(min=1990, max=2100))

        size = self.random_int(2, 7)
        two_seven_digits = [str(self.random_digit()) for _ in range(size)]
        two_seven_digits = "".join(two_seven_digits)
        return f"{two_seven_digits}/{year}"


class NumberProvider(BaseProvider):
    def random_bool(self, p: float = 0.5) -> bool:
        return self.random_element(OrderedDict([(True, p), (False, 1 - p)]))

    def _insert_dots_or_spaces(self, register: str, fmt: str) -> str:
        reversed_register = register[::-1]

        if fmt == "spaced":
            reversed_register = reversed_register[:3] + " " + reversed_register[3:]
        else:
            reversed_register = reversed_register[:3] + "." + reversed_register[3:]

        register = reversed_register[::-1]
        return register

    def cuit_cuil(self) -> str:
        prefix = self.random_element([20, 23, 24, 25, 26, 27, 30])
        inner = self.random_int(min=int(1e7), max=int(1e9 - 1))
        suffix = self.random_int(0, 10)

        cuit_cuil = f"{prefix}-{inner}-{suffix}"
        dashed = self.random_bool(p=0.1)
        if dashed:
            cuit_cuil = cuit_cuil.replace("-", "")

        return cuit_cuil

    def cbu(self) -> str:
        bank_code = self.random_element(bank_codes)
        nineteen_digits = [str(self.random_digit()) for _ in range(19)]
        return f"{bank_code}{''.join(nineteen_digits)}"

    def phone(self) -> str:
        phone_number = faker.phone_number()

        remove_prefix = self.random_bool(p=0.95)
        if remove_prefix:
            phone_number = re.sub(r"\+54 (?:9 )?", "", phone_number)

        fmt = self.random_element(
            OrderedDict([["numeric", 0.4], ["dashed", 0.4], ["spaced", 0.2]])
        )

        if fmt == "numeric":
            return re.sub(r"\s+", "", phone_number)

        if fmt == "dashed":
            return re.sub(r"\s+", "-", phone_number)

        return phone_number

    def register(self) -> str:
        n_digits = self.random_int(5, 6)
        digits = [str(self.random_digit()) for _ in range(n_digits)]
        digits = "".join(digits)

        fmt = self.random_element(
            OrderedDict([["dotted", 0.7], ["numeric", 0.2], ["spaced", 0.1]])
        )

        if fmt in ("dotted", "spaced"):
            digits = self._insert_dots_or_spaces(digits, fmt)

        return digits

    def savings_account(self) -> str:
        account_type = self.random_element(["0200", "0210"])

        prefix = [str(self.random_digit()) for _ in range(2)]
        prefix = "".join(prefix)

        nine_digits = [str(self.random_digit()) for _ in range(9)]
        nine_digits = "".join(nine_digits)

        three_digits = [str(self.random_digit()) for _ in range(3)]
        three_digits = "".join(three_digits)

        return f"{prefix}{account_type}{nine_digits}{three_digits}"


class PersonProvider(Provider):
    def random_bool(self, p: float = 0.5) -> bool:
        return self.random_element(OrderedDict([(True, p), (False, 1 - p)]))

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
        n_last_names = self.random_int(1, 4)
        last_names = " ".join([faker.last_name() for i in range(n_last_names)])

        name = f"{faker.first_name_nonbinary()} {last_names}"

        # initials
        initials = self.random_bool(p=0.75)
        if not initials:
            return name

        words = name.split()
        initials = [word[0] for word in words]

        delimiter = self.random_element(OrderedDict([[".", 0.25], [". ", 0.75]]))

        return delimiter.join(initials)

    def age(self) -> str:
        # TODO: add num2words to handle numbers in words
        in_years = self.random_bool(p=0.8)

        if in_years:
            age = self.random_int(min=1, max=100)
            return str(age)

        else:  # age in months
            age = self.random_int(min=1, max=12)
            return f"{age} meses" if age > 1 else f"{age} mes"

    def dni(self) -> str:
        dni = str(self.random_int(min=1_000_000, max=100_000_000))

        fmt = self.random_element(
            OrderedDict([("dotted", 0.7), ("numeric", 0.2), ("spaced", 0.1)])
        )

        if fmt in ("dotted", "spaced"):
            dni = self._insert_dots_or_spaces(dni, fmt)
        return dni

    def nationality(self) -> str:
        return self.random_element(nationalities)

    def studies(self) -> str:
        levels = ["primarios", "secundarios", "terciarios", "universitarios"]
        status = ["completos", "incompletos", "en curso"]

        level = self.random_element(levels)
        status = self.random_element(status)
        return f"estudios {level} {status}"


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

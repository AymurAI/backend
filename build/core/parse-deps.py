#!/bin/env python3
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("requirements", help="requirement file")
parser.add_argument(
    "--subpackage",
    "-s",
    help="coma separated package names",
    default="",
)

args = parser.parse_args()

distribution = args.subpackage.split(",")
distribution = ["default"] + distribution

if distribution == ["default"]:
    distribution += [""]

with open(args.requirements, "r") as file:
    lines = file.readlines()

packages = {}
section = "default"
for line in lines:
    line = line.strip()
    line = line.replace(" ", "")
    if section not in packages:
        packages[section] = []
    if not line:
        continue

    if line.startswith("[") and line.endswith("]"):
        section = line[1:-1]
        continue

    packages[section].append(line)

return_list = []
for key, values in packages.items():
    if key in distribution:
        return_list += values

print(" ".join(return_list))

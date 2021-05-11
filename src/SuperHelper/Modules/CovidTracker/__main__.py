import csv
import datetime as dt
import io
import json
import sys
import copy
import urllib.error as url_err
import urllib.request as url_req
import pathlib
import re

import numpy as np
import matplotlib.pyplot as plt
import dateutil.parser
import click

from SuperHelper.Core.Essentials import *

ModuleName: str = "CovidTracker"
logger, ModuleDir = initialise_module(ModuleName)
CacheDir = ModuleDir / "Cache"
CacheDir.mkdir(parents=True, exist_ok=True)
__name__ = f"SuperHelper.Modules.{ModuleName}"

origin_date = dt.datetime(day=2, month=12, year=2020)

__all__ = [
    "normalise_datetime",
    "create_source_url",
    "get_source_file",
    "parse_source_data",
    "extract_source_data",
    "get_country_data",
    "get_data_for_date",
    "cache_data",
    "main",
    "CacheDir",
]


def normalise_datetime(date_string: str) -> str:
    """Turns any date string into format MM-DD-YYYY.

    This function uses `dateutil.parser.parse` internally. Hence, most strings of digits are valid.

    Args:
        date_string (str): A date string.

    Returns:
        A date string in format MM-DD-YYYY.
    """
    try:
        return dateutil.parser.parse(date_string, dayfirst=True).strftime("%m-%d-%Y")
    except ValueError:
        raise ValueError("Invalid date format")


def create_source_url(date_string: str) -> str:
    """Creates the URL to source file of date.

    Args:
        date_string (str): A date string.

    Returns:
        A URL string of the source file.
    """
    if not re.match(r"^(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])-20\d\d$", date_string):
        raise ValueError("Invalid date format, must be MM-DD-YYY! Try using normalise_datetime()!")
    gh_branch_url = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master"
    source_path = "/csse_covid_19_data/csse_covid_19_daily_reports/"
    file_name = f"{date_string}.csv"
    return gh_branch_url + source_path + file_name


def get_source_file(url: str, force: bool = False) -> list[str]:
    """Downloads and saves source file.

    This function will look for cached source file, if any, then return. If `force` is set to `True`, this function
    will re-download and overwrite the cached file.

    Args:
        url (str): The URL to source file.
        force (bool): Whether to force re-download.

    Returns:
        A list of strings of the lines of the source file.
    """
    filename = pathlib.Path(url).name
    source_file_location = ModuleDir / "Cache" / filename
    if not force and source_file_location.is_file():
        with open(source_file_location) as fp:
            return fp.readlines()
    raw_data = list(url_req.urlopen(url))
    string_data = list(map(lambda s: str(s, "utf-8"), raw_data))
    with open(source_file_location, "w") as fp:
        fp.writelines(string_data)
    return string_data


latest_date = dt.datetime.today()
while True:
    try:
        get_source_file(create_source_url(latest_date.strftime("%m-%d-%Y")))
    except url_err.HTTPError:
        latest_date -= dt.timedelta(days=1)
    else:
        break


def parse_source_data(source_data: list[str]) -> list[str]:
    """Parses source data as CSV.

    Args:
        source_data (list[str]): A list of lines of source data.

    Returns:
        A list of CSV entries of the source file.
    """
    concat = "".join(source_data)
    buffer = io.StringIO(concat)
    csv_parsed_data = csv.reader(buffer)
    return list(csv_parsed_data)


def extract_source_data(parsed_data: list[str], cache_file: PathLike = None, force: bool = False) -> dict[str, list]:
    """Extracts information from the parsed source data.

    Args:
        parsed_data (list[str]): The parsed source data.
        cache_file (PathLike): Path to cached file.
        force (bool): Whether to force re-extraction.

    Returns:
        A dictionary of country-data pairs, where country is the name of a country, and data is a list of confirmed,
        death, recovered, and active COVID-19 cases of the country, respectively.
    """
    # Remove header
    parsed_data.pop(0)
    starting_index = 7
    number_of_field = 4
    if not force and cache_file is not None and pathlib.Path(cache_file).is_file():
        with open(cache_file) as fp:
            return json.load(fp)
    data = dict()
    for entry in parsed_data:
        entry = list(map(lambda s: "0" if s == "" else s, entry))
        country_name = entry[3]
        if country_name in data.keys():
            for i in range(number_of_field):
                data[country_name][i] += int(entry[starting_index + i])
        else:
            data[country_name] = list(map(int, entry[starting_index:starting_index + number_of_field]))
    if cache_file is not None:
        with open(cache_file, "w") as fp:
            json.dump(data, fp)
    return data


def get_data_for_date(date_string: str, force: bool = False) -> dict[str, list]:
    """Gets the extracted data for date.

    Args:
        date_string (str): A date string.
        force (bool): Whether to force re-download and re-extraction.

    Returns:
        A dictionary of country-data pairs, where country is the name of a country, and data is a list of confirmed,
        death, recovered, and active COVID-19 cases of the country, respectively.
    """
    if not re.match(r"^(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])-20\d\d$", date_string):
        raise ValueError("Invalid date format, must be MM-DD-YYY! Try using normalise_datetime()!")
    url = create_source_url(date_string)
    source_file = get_source_file(url, force)
    parsed_source_file = parse_source_data(source_file)
    cache_filename = CacheDir / f"extracted-{pathlib.Path(url).name.split('.')[0]}.json"
    return extract_source_data(parsed_source_file, cache_filename, force)


def get_country_data(country: str, start_date: dt.datetime = None, end_date: dt.datetime = None) -> dict[str, list]:
    """Gets data for a country over a range of days.

    Args:
        country (str): The name of the country.
        start_date (datetime): The starting date.
        end_date (datetime): The ending date.

    Returns:
        A dictionary of date-data pairs, where date is the date when the data is obtained, and data is a list of
        confirmed, death, recovered, and active COVID-19 cases of the country, respectively.
    """
    if end_date is None or end_date > latest_date:
        end_date = latest_date
    if start_date is None or start_date < origin_date:
        start_date = origin_date
    result = dict()
    for i in range((end_date - start_date).days + 1):
        date_string = (start_date + dt.timedelta(days=i)).strftime("%m-%d-%Y")
        data = get_data_for_date(date_string)
        country_data = data.get(country, None)
        if country_data is not None:
            result[date_string] = country_data
        else:
            raise ValueError(country)
    return result


def cache_data(no_of_days: int = 365, force: bool = False) -> None:
    """Downloads, extracts and cache data.

    This function is a helper function.

    Args:
        no_of_days (int): Number of days worth of data to download.
        force (bool): Whether to force re-download and re-extraction.

    Returns:
        None
    """
    date = copy.deepcopy(latest_date)
    date_string = date.strftime("%m-%d-%Y")
    if (date - origin_date).days < no_of_days:
        no_of_days = (date - origin_date).days
    for i in range(no_of_days):
        click.echo(f"\rDownloading for {date_string}... ({i + 1}/{no_of_days})", nl=False)
        try:
            get_data_for_date(date_string, force)
        except url_err.HTTPError:
            pass
        date -= dt.timedelta(days=1)
        date_string = date.strftime("%m-%d-%Y")
    click.echo()


def get_new_changes(country: str, date: dt.datetime) -> list:
    yesterday, today = get_country_data(country, date - dt.timedelta(days=1), date).values()
    yesterday = np.array(yesterday)
    today = np.array(today)
    return today - yesterday


def validate_date(value, *_, **__):
    try:
        if value == "latest":
            return latest_date.strftime("%m-%d-%Y")
        else:
            d = normalise_datetime(value)
            if dt.datetime.strptime(d, "%m-%d-%Y") > latest_date:
                logger.warning(f"Date for date '{d}' is not available. Using the latest data...")
                return latest_date.strftime("%m-%d-%Y")
            return d
    except ValueError:
        raise click.BadParameter("Invalid date format!")


def validate_number_of_days(value, *_, **__):
    try:
        if value == "max":
            return (latest_date - origin_date).days
        val = int(value)
        if val > (latest_date - origin_date).days:
            logger.warning(f"Number of days exceed the origin date. Using the maximum number of days...")
            return (latest_date - origin_date).days
        return val
    except ValueError:
        raise click.BadParameter("Invalid value, must be an integer!")


@click.group("covid")
def main():
    """Shows and plots COVID-19 data."""
    pass


@main.command("tally")
@click.option("-d", "--date", default="latest", help="The date of the tally.", type=validate_date, show_default=True)
@click.option("--no-change", default=False, help="Disable printing out daily changes.", is_flag=True, show_default=True)
@click.argument("countries", nargs=-1, type=str, required=True)
def tally(date, no_change, countries):
    """Shows COVID-19 tally for countries."""
    click.echo(f"Selected date (MM-DD-YYYY) is {date}")
    date_obj = dt.datetime.strptime(date, "%m-%d-%Y")
    data = []
    changes = []
    for ct in countries:
        try:
            data.append(get_country_data(ct, date_obj, date_obj)[date])
            if not no_change:
                changes.append(get_new_changes(ct, date_obj))
        except ValueError as ex:
            raise click.BadParameter(f"Country '{ex.args[0]}' is not found!")
    changes += [0] * (len(countries) - len(changes))
    header = f"|{'Country':^14}|{'Confirmed':^14}|{'Death':^14}|{'Recovered':^14}|{'Active':^14}|"
    click.echo("-" * len(header))
    click.echo(header)
    click.echo("-" * len(header))
    for ct, d, ch in zip(countries, data, changes):
        click.echo(f"|{ct:^14}|{d[0]:^14}|{d[1]:^14}|{d[2]:^14}|{d[3]:^14}|")
        if not no_change:
            ch = list(map(lambda n: f"({n if n < 0 else '+' + str(n)})", ch))
            click.echo(f"|{'':^14}|{ch[0]:^14}|{ch[1]:^14}|{ch[2]:^14}|{ch[3]:^14}|")
        click.echo("-" * len(header))
    sys.exit(0)


@main.command("plot")
@click.option("-e", "--end", default="latest", help="The end date of the tally.",
              type=validate_date, show_default=True)
@click.option("-n", "--number-of-days", default="max", type=validate_number_of_days,
              help="Number of days of data to plot.", show_default=True)
@click.option("-c", "--confirmed", default=False, is_flag=True,
              help="Whether to plot the number of confirmed cases.", show_default=True)
@click.option("-d", "--death", default=False, is_flag=True,
              help="Whether to plot the number of deaths.", show_default=True)
@click.option("-r", "--recovered", default=False, is_flag=True,
              help="Whether to plot the number of recovered cases.", show_default=True)
@click.option("-a", "--active", default=False, is_flag=True,
              help="Whether to plot the number of active cases.", show_default=True)
@click.option("-s", "--scale", default="log", type=click.Choice(["log", "linear"]))
@click.argument("country", type=str, required=True)
def plot(end, number_of_days, confirmed, death, recovered, active, country, scale):
    """Plots the COVID-19 tally of countries."""
    if not (confirmed or death or recovered or active):
        logger.warning("At least one plot type must be enabled!")
        sys.exit(1)
    click.echo(f"Selected end date (MM-DD-YYYY) is {end}")
    click.echo(f"Selected number of days is {number_of_days}")
    x_data = np.linspace(-(number_of_days - 1), 0, number_of_days)
    try:
        data = get_country_data(country, dateutil.parser.parse(end) - dt.timedelta(days=number_of_days - 1), dateutil
                                .parser.parse(end))
    except ValueError:
        raise click.BadParameter(f"Country '{country}' is not found!")
    if confirmed:
        plt.plot(x_data, np.array([x[0] for x in data.values()]), "b-", label="Confirmed")
    if death:
        plt.plot(x_data, np.array([x[1] for x in data.values()]), "k-", label="Death")
    if recovered:
        plt.plot(x_data, np.array([x[2] for x in data.values()]), "g-", label="Recovered")
    if active:
        plt.plot(x_data, np.array([x[3] for x in data.values()]), "r-", label="Active")
    plt.yscale(scale)
    plt.title("COVID-19 tally for " + country)
    plt.xlabel("Number of days since the latest report")
    plt.ylabel("Number of cases")
    plt.legend(loc="best")
    if not DEBUG:
        plt.show()
    sys.exit(0)


@main.command("cache")
@click.option("-f", "--force", is_flag=True, default=False, help="Whether to force re-download or re-extraction.")
@click.argument("days", default="max", type=validate_number_of_days)
def cache(days, force):
    """Pre-downloads and pre-extracts data to speed up further operations."""
    cache_data(days, force)
    sys.exit(0)

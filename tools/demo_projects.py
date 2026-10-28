"""Create six example projects on live public data, safe to run again.

Each project gets a connector to a real open data source (no key needed), exactly its own
three playbooks (screens built from the table functions, with Thai titles; every other
playbook in the catalog is switched off for the project, whatever the system switch says),
a knowledge category with public-domain PDF reports and reference articles, and a first
sync and run of every playbook. Three projects are for API use: each gets a read+run API
key limited to it, a client profile and a Postman environment (file mode 600; import it
together with docs/postman/api.postman_collection.json). Three are for the web: run them
from the project page.

  backend/.venv/bin/python tools/demo_projects.py --server http://127.0.0.1:8700 \\
      --email admin@example.com [--only seismic-watch] [--skip-sync] [--skip-runs]

The admin password comes from MINDGRID_ADMIN_PASSWORD or a prompt. Needs the worker.
"""

import argparse
import getpass
import json
import os
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import mgapi

OWID_AGGREGATES = [
    "OWID_AFR",
    "OWID_ASI",
    "OWID_EU27",
    "OWID_EUR",
    "OWID_HIC",
    "OWID_LIC",
    "OWID_LMC",
    "OWID_NAM",
    "OWID_OCE",
    "OWID_SAM",
    "OWID_UMC",
    "OWID_WRL",
]
DOC_LIMIT = 25_000  # characters kept per reference article (PDFs are uploaded whole)


@dataclass(frozen=True)
class Screen:
    """A playbook: read a dataset, keep rows meeting `where`, rank, keep the top rows."""

    id: str
    title: str
    summary: str
    th: tuple[str, str]
    dataset: str
    where: list[dict[str, Any]]
    rank_by: str
    columns: list[str]
    descending: bool = True
    params: dict[str, dict[str, Any]] = field(default_factory=dict[str, dict[str, Any]])

    def spec(self) -> dict[str, Any]:
        top = {
            "type": "integer",
            "default": 20,
            "minimum": 1,
            "maximum": 500,
            "doc": "Rows returned.",
        }
        return {
            "id": self.id,
            "version": 1,
            "status": "active",
            "title": self.title,
            "summary": self.summary,
            "translations": {"th": {"title": self.th[0], "summary": self.th[1]}},
            "inputs": {
                "data": {
                    "type": "dataset",
                    "required": False,
                    "default": self.dataset,
                    "doc": "Dataset name (the run pins its newest version).",
                }
            },
            "params": {**self.params, "top_n": top},
            "steps": [
                {"id": "table", "fn": "core.table.from_dataset", "with": {"frame": "$inputs.data"}},
                {
                    "id": "kept",
                    "fn": "core.table.filter",
                    "with": {"rows": "$steps.table.rows", "where": self.where},
                },
                {
                    "id": "ranked",
                    "fn": "core.table.sort",
                    "with": {
                        "rows": "$steps.kept.rows",
                        "by": self.rank_by,
                        "descending": self.descending,
                    },
                },
                {
                    "id": "top",
                    "fn": "core.table.top",
                    "with": {"rows": "$steps.ranked.rows", "n": "$params.top_n"},
                },
                {
                    "id": "shown",
                    "fn": "core.table.select",
                    "with": {"rows": "$steps.top.rows", "columns": self.columns},
                },
            ],
            "outputs": {"rows": "$steps.shown.rows", "matched": "$steps.kept.count"},
        }


@dataclass(frozen=True)
class Project:
    slug: str
    name: str
    description: str
    connector: str
    spec: dict[str, Any]
    every_minutes: int
    screens: list[Screen]
    knowledge: tuple[str, str]  # category name, description
    docs: list[tuple[str, str]]  # (title, source URL: a PDF, a Wikipedia page or a text file)
    api: bool  # an API key and a Postman environment
    question: str  # the sample question the Postman environment asks the knowledge


def _wiki(title: str) -> tuple[str, str]:
    return title, f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"


def _num(doc: str, default: float) -> dict[str, Any]:
    return {"type": "number", "default": default, "doc": doc}


def _meteo(city: str, lat: float, lon: float) -> dict[str, Any]:
    daily = (
        "temperature_2m_max,apparent_temperature_max,precipitation_sum,uv_index_max,"
        "wind_speed_10m_max"
    )
    return {
        "dataset": f"weather-{city}",
        "path": "/v1/forecast",
        "format": "json",
        "records_path": "daily",
        "title": f"16-day forecast, {city.replace('-', ' ')}",
        "query": {
            "latitude": str(lat),
            "longitude": str(lon),
            "daily": daily,
            "timezone": "Asia/Bangkok",
            "forecast_days": "16",
        },
    }


def _air(city: str, lat: float, lon: float) -> dict[str, Any]:
    return {
        "dataset": f"air-{city}",
        "path": "/v1/air-quality",
        "format": "json",
        "records_path": "hourly",
        "title": f"Hourly air quality, {city.replace('-', ' ')}",
        "query": {
            "latitude": str(lat),
            "longitude": str(lon),
            "hourly": ",".join(AIR_COLUMNS[1:]),
            "timezone": "Asia/Bangkok",
            "past_days": "2",
            "forecast_days": "5",
        },
    }


QUAKE_COLUMNS = ["time", "place", "mag", "magType", "depth", "latitude", "longitude", "id"]
REPO_COLUMNS = [
    "full_name",
    "stargazers_count",
    "forks_count",
    "open_issues_count",
    "language",
    "pushed_at",
    "html_url",
]
PLANET_COLUMNS = [
    "pl_name",
    "hostname",
    "disc_year",
    "discoverymethod",
    "pl_rade",
    "pl_bmasse",
    "pl_orbper",
    "pl_eqt",
    "sy_dist",
]
WEATHER_COLUMNS = [
    "time",
    "temperature_2m_max",
    "apparent_temperature_max",
    "precipitation_sum",
    "uv_index_max",
    "wind_speed_10m_max",
]
AIR_COLUMNS = ["time", "pm2_5", "pm10", "us_aqi", "ozone", "nitrogen_dioxide"]
OWID_QUERY = {"v": "1", "csvType": "full", "useColumnShortNames": "true"}
EXO_QUERY = (
    "select pl_name,hostname,disc_year,discoverymethod,pl_rade,pl_bmasse,pl_orbper,"
    "pl_eqt,sy_dist from ps where default_flag=1"
)

PROJECTS = [
    Project(
        "seismic-watch",
        "Seismic Watch",
        "Earthquakes worldwide from the USGS feed (past week and significant events), "
        "screened for strong and shallow quakes, with seismology references.",
        "usgs",
        {
            "base_url": "https://earthquake.usgs.gov",
            "resources": [
                {
                    "dataset": "quakes-week",
                    "path": "/earthquakes/feed/v1.0/summary/all_week.csv",
                    "title": "Every earthquake, past 7 days",
                },
                {
                    "dataset": "quakes-significant-month",
                    "path": "/earthquakes/feed/v1.0/summary/significant_month.csv",
                    "title": "Significant earthquakes, past 30 days",
                },
            ],
        },
        60,
        [
            Screen(
                "seismic.strong-quakes",
                "Strong quakes",
                "Quakes at or above a magnitude, strongest first.",
                ("แผ่นดินไหวรุนแรง", "แผ่นดินไหวที่ขนาดไม่ต่ำกว่าเกณฑ์ เรียงจากแรงสุด"),
                "quakes-week",
                [{"column": "mag", "op": "ge", "value": "$params.min_mag"}],
                "mag",
                QUAKE_COLUMNS,
                params={"min_mag": _num("Lowest magnitude kept.", 4.5)},
            ),
            Screen(
                "seismic.shallow-strong",
                "Shallow strong quakes",
                "Strong quakes close to the surface (most damaging), strongest first.",
                ("แผ่นดินไหวแรงและตื้น", "แผ่นดินไหวแรงที่ลึกไม่มาก (สร้างความเสียหายมาก)"),
                "quakes-week",
                [
                    {"column": "mag", "op": "ge", "value": "$params.min_mag"},
                    {"column": "depth", "op": "le", "value": "$params.max_depth"},
                ],
                "mag",
                QUAKE_COLUMNS,
                params={
                    "min_mag": _num("Lowest magnitude kept.", 5.0),
                    "max_depth": _num("Deepest hypocentre kept (km).", 70),
                },
            ),
            Screen(
                "seismic.significant-month",
                "Significant quakes this month",
                "The USGS list of significant earthquakes of the past 30 days, strongest first.",
                ("แผ่นดินไหวสำคัญในเดือนนี้", "แผ่นดินไหวที่ USGS จัดว่าสำคัญใน 30 วันล่าสุด เรียงจากแรงสุด"),
                "quakes-significant-month",
                [{"column": "type", "op": "eq", "value": "earthquake"}],
                "mag",
                QUAKE_COLUMNS,
            ),
        ],
        ("Seismology", "How earthquakes are measured, the hazard maps and how to prepare."),
        [
            (
                "USGS National Seismic Hazard Maps (fact sheet)",
                "https://pubs.usgs.gov/fs/2008/3018/pdf/FS08-3018_508.pdf",
            ),
            (
                "USGS Putting Down Roots in Earthquake Country (handbook)",
                "https://pubs.usgs.gov/gip/2005/15/gip-15.pdf",
            ),
            _wiki("Moment magnitude scale"),
            _wiki("Earthquake"),
            _wiki("Tsunami"),
            _wiki("Seismic intensity scales"),
        ],
        api=True,
        question="How should a household prepare for a strong earthquake?",
    ),
    Project(
        "open-source-pulse",
        "Open Source Pulse",
        "Repositories of major open-source organisations from the GitHub API: the most "
        "starred and the ones with the largest open-issue backlog, with project READMEs.",
        "github",
        {
            "base_url": "https://api.github.com",
            "resources": [
                {
                    "dataset": f"repos-{org}",
                    "path": f"/orgs/{org}/repos",
                    "format": "json",
                    "query": {"per_page": "100", "sort": "updated"},
                    "title": f"Repositories of {org}",
                }
                for org in ("python", "nodejs", "rust-lang")
            ],
        },
        360,
        [
            Screen(
                "oss.most-starred",
                "Most starred repositories",
                "Active (not archived) repositories, most stars first.",
                ("repository ที่ได้ดาวมากที่สุด", "repository ที่ยังเปิดใช้งาน เรียงตามจำนวนดาว"),
                "repos-python",
                [{"column": "archived", "op": "eq", "value": False}],
                "stargazers_count",
                REPO_COLUMNS,
            ),
            Screen(
                "oss.issue-backlog",
                "Largest issue backlogs",
                "Active repositories with many open issues, largest backlog first.",
                ("issue ค้างมากที่สุด", "repository ที่ยังเปิดใช้งานและมี issue ค้างมาก"),
                "repos-python",
                [
                    {"column": "archived", "op": "eq", "value": False},
                    {"column": "open_issues_count", "op": "ge", "value": "$params.min_open"},
                ],
                "open_issues_count",
                REPO_COLUMNS,
                params={"min_open": _num("Fewest open issues kept.", 20)},
            ),
            Screen(
                "oss.most-forked",
                "Most forked repositories",
                "Active repositories with many forks (others building on them), most forks first.",
                ("repository ที่ถูก fork มากที่สุด", "repository ที่ยังเปิดใช้งานและมีคนนำไปต่อยอดมาก"),
                "repos-rust-lang",
                [
                    {"column": "archived", "op": "eq", "value": False},
                    {"column": "forks_count", "op": "ge", "value": "$params.min_forks"},
                ],
                "forks_count",
                REPO_COLUMNS,
                params={"min_forks": _num("Fewest forks kept.", 50)},
            ),
        ],
        ("Project docs", "Secure development practice and the flagship repositories' READMEs."),
        [
            (
                "NIST SP 800-218 Secure Software Development Framework",
                "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218.pdf",
            ),
            ("CPython README", "https://raw.githubusercontent.com/python/cpython/main/README.rst"),
            ("Node.js README", "https://raw.githubusercontent.com/nodejs/node/main/README.md"),
            ("Rust README", "https://raw.githubusercontent.com/rust-lang/rust/master/README.md"),
            _wiki("Open-source software"),
        ],
        api=True,
        question="What practices protect the software supply chain?",
    ),
    Project(
        "climate-emissions",
        "Climate & Emissions",
        "Carbon dioxide emissions by country from Our World in Data (total and per person), "
        "screened for the largest emitters of a year, with climate references.",
        "owid",
        {
            "base_url": "https://ourworldindata.org",
            "resources": [
                {
                    "dataset": "co2-annual",
                    "path": "/grapher/annual-co2-emissions-per-country.csv",
                    "query": OWID_QUERY,
                    "title": "Annual CO2 emissions per country (tonnes)",
                },
                {
                    "dataset": "co2-per-capita",
                    "path": "/grapher/co-emissions-per-capita.csv",
                    "query": OWID_QUERY,
                    "title": "CO2 emissions per person (tonnes)",
                },
            ],
        },
        1440,
        [
            Screen(
                "climate.top-emitters",
                "Largest emitters of a year",
                "Countries (not regions) ranked by total CO2 emissions in one year.",
                ("ประเทศที่ปล่อย CO2 มากที่สุด", "จัดอันดับประเทศตามปริมาณ CO2 ทั้งหมดในปีที่เลือก"),
                "co2-annual",
                [
                    {"column": "year", "op": "eq", "value": "$params.year"},
                    {"column": "code", "op": "not_in", "value": OWID_AGGREGATES},
                ],
                "emissions_total",
                ["entity", "code", "year", "emissions_total"],
                params={"year": _num("Year ranked.", 2024)},
            ),
            Screen(
                "climate.per-person",
                "Highest emissions per person",
                "Countries ranked by CO2 emissions per person in one year.",
                ("ปล่อย CO2 ต่อคนสูงสุด", "จัดอันดับประเทศตามปริมาณ CO2 ต่อประชากรหนึ่งคน"),
                "co2-per-capita",
                [
                    {"column": "year", "op": "eq", "value": "$params.year"},
                    {"column": "code", "op": "not_in", "value": OWID_AGGREGATES},
                ],
                "emissions_total_per_capita",
                ["entity", "code", "year", "emissions_total_per_capita"],
                params={"year": _num("Year ranked.", 2024)},
            ),
            Screen(
                "climate.country-trend",
                "One country over the years",
                "Total CO2 emissions of one country (ISO code) since a year, newest first.",
                ("แนวโน้ม CO2 รายประเทศ", "ปริมาณ CO2 ของประเทศที่เลือก (รหัส ISO) ตั้งแต่ปีที่กำหนด"),
                "co2-annual",
                [
                    {"column": "code", "op": "eq", "value": "$params.country"},
                    {"column": "year", "op": "ge", "value": "$params.since"},
                ],
                "year",
                ["entity", "code", "year", "emissions_total"],
                params={
                    "country": {"type": "string", "default": "THA", "doc": "ISO 3166 alpha-3."},
                    "since": _num("First year kept.", 1990),
                },
            ),
        ],
        ("Climate science", "Greenhouse gases, targets and how emissions are counted."),
        [
            (
                "EPA Inventory of U.S. Greenhouse Gas Emissions 2023 (executive summary)",
                "https://www.epa.gov/system/files/documents/2023-04/"
                "US-GHG-Inventory-2023-Chapter-Executive-Summary.pdf",
            ),
            _wiki("Greenhouse gas emissions"),
            _wiki("Paris Agreement"),
            _wiki("Carbon dioxide in the atmosphere of Earth"),
            _wiki("Carbon footprint"),
        ],
        api=True,
        question="Which sectors emit the most greenhouse gases?",
    ),
    Project(
        "exoplanet-explorer",
        "Exoplanet Explorer",
        "Confirmed planets beyond the Solar System from the NASA Exoplanet Archive: "
        "Earth-sized worlds and the nearest systems, with astronomy references.",
        "nasa-exoplanets",
        {
            "base_url": "https://exoplanetarchive.ipac.caltech.edu",
            "resources": [
                {
                    "dataset": "planets",
                    "path": "/TAP/sync",
                    "query": {"query": EXO_QUERY, "format": "csv"},
                    "title": "Confirmed exoplanets (one row per planet)",
                }
            ],
        },
        1440,
        [
            Screen(
                "exo.earth-sized",
                "Earth-sized planets",
                "Planets between two radii (in Earth radii), nearest first.",
                ("ดาวเคราะห์ขนาดใกล้โลก", "ดาวเคราะห์ที่รัศมีอยู่ในช่วงที่กำหนด เรียงจากใกล้ที่สุด"),
                "planets",
                [
                    {"column": "pl_rade", "op": "ge", "value": "$params.min_radius"},
                    {"column": "pl_rade", "op": "le", "value": "$params.max_radius"},
                ],
                "sy_dist",
                PLANET_COLUMNS,
                descending=False,
                params={
                    "min_radius": _num("Smallest radius kept (Earth radii).", 0.8),
                    "max_radius": _num("Largest radius kept (Earth radii).", 1.5),
                },
            ),
            Screen(
                "exo.temperate",
                "Temperate planets",
                "Planets whose equilibrium temperature is between two values (kelvin), "
                "nearest first.",
                ("ดาวเคราะห์อุณหภูมิพอเหมาะ", "ดาวเคราะห์ที่อุณหภูมิสมดุลอยู่ในช่วงที่กำหนด"),
                "planets",
                [
                    {"column": "pl_eqt", "op": "ge", "value": "$params.min_temp"},
                    {"column": "pl_eqt", "op": "le", "value": "$params.max_temp"},
                ],
                "sy_dist",
                PLANET_COLUMNS,
                descending=False,
                params={
                    "min_temp": _num("Coolest kept (K).", 200),
                    "max_temp": _num("Warmest kept (K).", 320),
                },
            ),
            Screen(
                "exo.recent-discoveries",
                "Recent discoveries",
                "Planets confirmed since a year, newest first.",
                ("ดาวเคราะห์ที่เพิ่งค้นพบ", "ดาวเคราะห์ที่ยืนยันการค้นพบตั้งแต่ปีที่กำหนด เรียงจากใหม่สุด"),
                "planets",
                [{"column": "disc_year", "op": "ge", "value": "$params.since"}],
                "disc_year",
                PLANET_COLUMNS,
                params={"since": _num("First discovery year kept.", 2024)},
            ),
        ],
        ("Astronomy", "How exoplanets are found and what makes one habitable."),
        [
            (
                "NASA Kepler Data Validation I: vetting transiting planet candidates",
                "https://ntrs.nasa.gov/api/citations/20180001990/downloads/20180001990.pdf",
            ),
            (
                "NASA Habitable-Zone Exoplanet Observatory (HabEx) architecture",
                "https://ntrs.nasa.gov/api/citations/20180007664/downloads/20180007664.pdf",
            ),
            _wiki("Exoplanet"),
            _wiki("Habitable zone"),
            _wiki("Methods of detecting exoplanets"),
            _wiki("Kepler space telescope"),
        ],
        api=False,
        question="How are transiting planet candidates vetted?",
    ),
    Project(
        "city-weather-risk",
        "City Weather Risk",
        "16-day forecasts for five Thai cities from Open-Meteo: heat-stress days and "
        "heavy-rain days, with weather references.",
        "open-meteo",
        {
            "base_url": "https://api.open-meteo.com",
            "resources": [
                _meteo("bangkok", 13.75, 100.50),
                _meteo("chiang-mai", 18.79, 98.98),
                _meteo("phuket", 7.88, 98.39),
                _meteo("khon-kaen", 16.43, 102.83),
                _meteo("hat-yai", 7.01, 100.47),
            ],
        },
        180,
        [
            Screen(
                "weather.heat-days",
                "Heat-stress days",
                "Days whose feels-like maximum reaches a threshold, hottest first.",
                ("วันที่ร้อนจัด", "วันที่อุณหภูมิที่รู้สึกได้สูงถึงเกณฑ์ เรียงจากร้อนที่สุด"),
                "weather-bangkok",
                [{"column": "apparent_temperature_max", "op": "ge", "value": "$params.min_feels"}],
                "apparent_temperature_max",
                WEATHER_COLUMNS,
                params={"min_feels": _num("Lowest feels-like maximum kept (°C).", 38)},
            ),
            Screen(
                "weather.heavy-rain",
                "Heavy-rain days",
                "Days with at least a rainfall amount, wettest first.",
                ("วันที่ฝนตกหนัก", "วันที่ปริมาณฝนถึงเกณฑ์ เรียงจากฝนมากที่สุด"),
                "weather-bangkok",
                [{"column": "precipitation_sum", "op": "ge", "value": "$params.min_rain"}],
                "precipitation_sum",
                WEATHER_COLUMNS,
                params={"min_rain": _num("Least rainfall kept (mm).", 10)},
            ),
            Screen(
                "weather.high-uv",
                "High-UV days",
                "Days whose UV index reaches a level, highest first.",
                ("วันที่ UV สูง", "วันที่ดัชนี UV สูงถึงเกณฑ์ เรียงจากสูงสุด"),
                "weather-bangkok",
                [{"column": "uv_index_max", "op": "ge", "value": "$params.min_uv"}],
                "uv_index_max",
                WEATHER_COLUMNS,
                params={"min_uv": _num("Lowest UV index kept (6 = high, 8 = very high).", 6)},
            ),
        ],
        ("Weather and health", "Heat stress, ultraviolet light and the Thai climate."),
        [
            (
                "EPA Excessive Heat Events Guidebook",
                "https://www.epa.gov/sites/default/files/2016-03/documents/eheguide_final.pdf",
            ),
            (
                "EPA A Guide to the UV Index",
                "https://www.epa.gov/sites/default/files/documents/uviguide.pdf",
            ),
            ("NWS Heat Index equation", "https://www.weather.gov/media/epz/wxcalc/heatIndex.pdf"),
            _wiki("Heat index"),
            _wiki("Ultraviolet index"),
            _wiki("Climate of Thailand"),
            _wiki("Monsoon"),
        ],
        api=False,
        question="What should people do during an excessive heat event?",
    ),
    Project(
        "thai-air-quality",
        "Thai Air Quality",
        "Hourly PM2.5, PM10 and US AQI for five Thai cities from the Open-Meteo air-quality "
        "model (two days back, five ahead): hours over the Thai PM2.5 standard, unhealthy "
        "hours and clean-air hours, with EPA air-quality references.",
        "open-meteo-air",
        {
            "base_url": "https://air-quality-api.open-meteo.com",
            "resources": [
                _air("chiang-mai", 18.79, 98.98),
                _air("chiang-rai", 19.91, 99.83),
                _air("bangkok", 13.75, 100.50),
                _air("khon-kaen", 16.43, 102.83),
                _air("hat-yai", 7.01, 100.47),
            ],
        },
        60,
        [
            Screen(
                "air.pm25-over-standard",
                "PM2.5 over the Thai standard",
                "Hours whose PM2.5 reaches a level (the Thai 24-hour standard is 37.5 µg/m³), "
                "worst first.",
                ("PM2.5 เกินมาตรฐานไทย", "ชั่วโมงที่ PM2.5 ถึงเกณฑ์ (มาตรฐาน 24 ชม. ของไทย 37.5 µg/m³)"),
                "air-bangkok",
                [{"column": "pm2_5", "op": "ge", "value": "$params.min_pm25"}],
                "pm2_5",
                AIR_COLUMNS,
                params={"min_pm25": _num("Lowest PM2.5 kept (µg/m³).", 37.5)},
            ),
            Screen(
                "air.unhealthy-hours",
                "Unhealthy air hours",
                "Hours whose US AQI reaches a level (101 = unhealthy for sensitive groups), "
                "worst first.",
                ("ชั่วโมงที่อากาศไม่ดีต่อสุขภาพ", "ชั่วโมงที่ค่า AQI ถึงเกณฑ์ (101 = เริ่มมีผลต่อกลุ่มเสี่ยง)"),
                "air-bangkok",
                [{"column": "us_aqi", "op": "ge", "value": "$params.min_aqi"}],
                "us_aqi",
                AIR_COLUMNS,
                params={"min_aqi": _num("Lowest US AQI kept.", 101)},
            ),
            Screen(
                "air.clean-hours",
                "Clean-air hours",
                "Hours whose US AQI stays at or under a level (50 = good), cleanest first: "
                "when to be outdoors.",
                ("ชั่วโมงที่อากาศดี", "ชั่วโมงที่ค่า AQI ไม่เกินเกณฑ์ (50 = ดี) เหมาะกับกิจกรรมกลางแจ้ง"),
                "air-khon-kaen",
                [{"column": "us_aqi", "op": "le", "value": "$params.max_aqi"}],
                "us_aqi",
                AIR_COLUMNS,
                descending=False,
                params={"max_aqi": _num("Highest US AQI kept.", 50)},
            ),
        ],
        ("Air quality", "The Air Quality Index, particle pollution and health."),
        [
            (
                "EPA Technical Assistance Document for Reporting the AQI",
                "https://document.airnow.gov/"
                "technical-assistance-document-for-the-reporting-of-daily-air-quailty.pdf",
            ),
            (
                "EPA A Guide to Air Quality and Your Health",
                "https://www.airnow.gov/sites/default/files/2018-04/aqi_brochure_02_14_0.pdf",
            ),
            _wiki("Air quality index"),
            _wiki("Particulates"),
            _wiki("Haze in Southeast Asia"),
        ],
        api=False,
        question="What does an AQI above 150 mean for health?",
    ),
]


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"user-agent": mgapi.USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(req, timeout=180) as res:  # noqa: S310 - fixed https sources
        data: bytes = res.read()
        return data


def _fetch(url: str) -> str:
    return _download(url).decode("utf-8", errors="replace")


def _document(slug: str, index: int, title: str, url: str) -> mgapi.Upload:
    """A reference as uploaded: a PDF as published, else markdown text of a Wikipedia
    article (plain text) or of a raw file."""
    if url.lower().endswith(".pdf"):
        data = _download(url)
        if not data.startswith(b"%PDF-"):
            raise SystemExit(f"{url} did not return a PDF")
        return mgapi.Upload(title, f"{slug}-{index}.pdf", data, "application/pdf")
    if "wikipedia.org/wiki/" in url:
        page = url.rsplit("/", 1)[1]
        query = urllib.parse.urlencode(
            {
                "action": "query",
                "prop": "extracts",
                "explaintext": "1",
                "redirects": "1",
                "format": "json",
                "titles": page.replace("_", " "),
            }
        )
        pages = json.loads(_fetch(f"https://en.wikipedia.org/w/api.php?{query}"))["query"]
        text = next(iter(pages["pages"].values())).get("extract", "")
        licence = "Wikipedia, CC BY-SA 4.0"
    else:
        text, licence = _fetch(url), "the project's own licence"
    body = f"# {title}\n\nSource: {url} ({licence})\n\n{text[:DOC_LIMIT]}\n"
    return mgapi.Upload(title, f"{slug}-{index}.md", body.encode())


def _catalog(api: mgapi.Client) -> dict[str, dict[str, Any]]:
    return {p["id"]: p for p in api.call("GET", "playbooks")}


def _playbooks(api: mgapi.Client, pid: str, project: Project) -> list[dict[str, Any]]:
    """Switch on the project's own screens and switch off every other playbook for it
    (a project's choice wins over the system switch), so no other topic leaks in."""
    known = _catalog(api)
    for screen in project.screens:
        if screen.id not in known:
            api.call("POST", "admin/playbooks", screen.spec())
    known = _catalog(api)
    mine = {s.id for s in project.screens}
    for playbook_id in known:
        body = {"enabled": playbook_id in mine, "params": {}, "version": None}
        api.call("PUT", f"projects/{pid}/playbooks/{playbook_id}", body)
    on = [p["id"] for p in api.call("GET", f"playbooks?project_id={pid}") if p["enabled"]]
    if set(on) != mine:
        raise SystemExit(f"{project.slug}: playbooks on {sorted(on)}, expected {sorted(mine)}")
    print(f"playbooks    on: {', '.join(sorted(mine))}; {len(known) - len(mine)} others off")
    return [known[s.id] for s in project.screens]


def _knowledge(api: mgapi.Client, pid: str, project: Project) -> None:
    name, description = project.knowledge
    slug = name.lower().replace(" ", "-")
    category = mgapi.ensure_category(api, pid, slug, name, description)
    existing = {d["title"] for d in api.call("GET", f"categories/{category}/documents")}
    added = sum(
        mgapi.upload_document(api, category, _document(slug, i, title, url))
        for i, (title, url) in enumerate(project.docs)
        if title not in existing
    )
    pdfs = sum(url.lower().endswith(".pdf") for _, url in project.docs)
    print(f"knowledge    {name}: {len(project.docs)} document(s) ({pdfs} PDF), {added} new")


def api_brand(server: str) -> str:
    """The product name the server shows (never written in code)."""
    return str(json.loads(_fetch(f"{server}/v1/meta/brand"))["name"])


def _environment_file(slug: str) -> Path:
    from mindgrid.interfaces.remote import profiles  # noqa: PLC0415 - needs the backend venv

    return profiles.remote_config.config_dir() / "postman" / f"{slug}.postman_environment.json"


def _saved_key(path: Path, server: str) -> tuple[str, str] | None:
    """The key id and private key an earlier run against this server wrote to the file."""
    if not path.exists():
        return None
    values = {v["key"]: v["value"] for v in json.loads(path.read_text())["values"]}
    if values.get("base_url") != server:
        return None
    return values["key_id"], values["private_key"]


def _postman_environment(server: str, project: Project, key: tuple[str, str]) -> Path:
    """Write (or refresh) the project's Postman environment, file mode 600."""
    from mindgrid.interfaces.remote import profiles  # noqa: PLC0415 - needs the backend venv

    key_id, private_key = key
    values = [
        {"key": "base_url", "value": server, "type": "default", "enabled": True},
        {"key": "project_slug", "value": project.slug, "type": "default", "enabled": True},
        {"key": "question", "value": project.question, "type": "default", "enabled": True},
        {"key": "key_id", "value": key_id, "type": "default", "enabled": True},
        {"key": "private_key", "value": private_key, "type": "secret", "enabled": True},
    ]
    brand = api_brand(server)
    body = {
        "name": f"{brand} · {project.name}",
        "values": values,
        "_postman_variable_scope": "environment",
    }
    path = _environment_file(project.slug)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    profiles.write_private(path, json.dumps(body, indent=2))
    return path


def _verify(api: mgapi.Client, pid: str, playbooks: list[dict[str, Any]]) -> None:
    """Run every screen on its own defaults."""
    for p in playbooks:
        run = mgapi.run_playbook(api, pid, p, {}, {})
        rows = len((run.get("outputs") or {}).get("rows") or [])
        print(
            f"run          {p['id']}: {run['status']} matched={mgapi.result_count(run)} "
            f"shown={rows} {run.get('error', '')[:120]}"
        )


def _provision(
    api: mgapi.Client, me: dict[str, Any], project: Project, args: argparse.Namespace
) -> None:
    pid = mgapi.ensure_project(api, project.slug, project.name, project.description)
    mgapi.save_connector(api, pid, project.connector, project.spec, project.every_minutes)
    if not args.skip_sync:
        mgapi.sync(api, pid, project.connector, args.wait)
    playbooks = _playbooks(api, pid, project)
    _knowledge(api, pid, project)
    if project.api:
        want = mgapi.KeyRequest(
            me["id"], pid, f"{project.slug} client", project.slug, args.key_days
        )
        issued = mgapi.issue_project_key(api, want)
        key = (
            (issued["key"]["key_id"], issued["private_key_pem"])
            if issued
            else _saved_key(_environment_file(project.slug), api.server)
        )
        if key:
            path = _postman_environment(api.server, project, key)
            print(f"postman      environment -> {mgapi.shown_path(path)}")
        else:
            print(
                f"postman      no environment file for this server: revoke the key "
                f"'{want.name}' on the API keys page and run again for a new one"
            )
    if not args.skip_runs:
        _verify(api, pid, playbooks)
    print(f"done         {api.server}/projects/{pid}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--server", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--only", action="append", default=[], help="Project slug (repeatable)")
    parser.add_argument("--wait", type=int, default=20, help="Minutes to wait for each sync")
    parser.add_argument("--key-days", type=int, default=90)
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--skip-runs", action="store_true")
    args = parser.parse_args()
    api = mgapi.Client(args.server)
    password = os.environ.get("MINDGRID_ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    me = api.sign_in(args.email, password)
    for project in PROJECTS:
        if not args.only or project.slug in args.only:
            _provision(api, me, project, args)


if __name__ == "__main__":
    sys.exit(main())

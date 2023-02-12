#!/usr/bin/env python3

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
import datetime
from pathlib import Path
import shutil
import tempfile
from typing import IO, Optional, Sequence, Union

import click
from dateutil import tz
import jinja2
import yaml


THISDIR = Path(__file__).parent

TZINFO = tz.gettz('Pacific/Auckland')
START_WEEK = datetime.datetime(2021, 4, 11, tzinfo=TZINFO)


@dataclass(frozen=True, eq=True)
class Chore:
    id: str
    name: str

    def __str__(self) -> str:
        return self.id

    @classmethod
    def from_json(cls, d: Union[dict[str, str], str]) -> Chore:
        if isinstance(d, dict):
            return cls(d['id'], d.get('name') or d['id'].title())

        return cls(d, d.title())


@dataclass(frozen=True, eq=True)
class ChoreGroup:
    id: str
    name: str

    def __str__(self) -> str:
        return self.id

    @classmethod
    def from_json(cls, id: str, d: dict) -> ChoreGroup:
        return cls(
            id=id,
            name=d.get('name') or id.title(),
        )


def load_chores(
    config_filename: str
) -> dict[ChoreGroup, tuple[list[Chore], list[str]]]:
    with open(THISDIR / config_filename) as f:
        config = yaml.safe_load(f)

    return {
        ChoreGroup.from_json(id, d): (
            [Chore.from_json(chore) for chore in d['chores']],
            d['people']
        )
        for id, d in config.items()
    }


def assign_chores(
    offset: int, chores: Sequence[Chore], people: Sequence[str]
) -> dict[Chore, str]:
    num_people = len(people)
    return {
        chore: people[(i + offset) % num_people]
        for i, chore in enumerate(chores)
    }


def get_current_date() -> datetime.datetime:
    return datetime.datetime.now(TZINFO)


def offset(date: datetime.datetime) -> int:
    return (date - START_WEEK).days // 7


def week_sunday(date: datetime.datetime) -> datetime.datetime:
    days = (6 - date.weekday()) % 7
    return date + datetime.timedelta(days=days)


def fmtdate(date: datetime.datetime) -> str:
    return date.strftime('%A, %-d %B %Y')


class Builder(AbstractContextManager):
    output_dir: Path
    env: jinja2.Environment
    tempdir: Path
    _tempdir: tempfile.TemporaryDirectory

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(THISDIR / 'templates'),
            autoescape=jinja2.select_autoescape()
        )

        self._tempdir = tempfile.TemporaryDirectory()
        self.tempdir = Path(self._tempdir.name)

    def __enter__(self) -> Builder:
        return self

    def __exit__(self, exc, exc_type, tb):
        if not exc:
            if self.output_dir.exists():
                shutil.rmtree(self.output_dir)
            shutil.move(self.tempdir, self.output_dir)
        else:
            self._tempdir.cleanup()

    def url_path(self, path: str) -> str:
        return '/' + path.lstrip('/')

    def render_template(
        self,
        template: str,
        path: str,
        **kwargs
    ) -> None:
        kw = {
            'url_path': self.url_path,
        }
        kw.update(kwargs)
        destdir = self.tempdir / path.lstrip('/')
        destdir.mkdir(parents=True, exist_ok=True)
        with open(destdir / 'index.html', 'w') as f:
            f.write(self.env.get_template(template).render(**kw))

    def copy_dir(self, dir: Union[str, Path], dest_path: str) -> None:
        shutil.copytree(dir, self.tempdir / dest_path.lstrip('/'))

    def open(self, path: str, *args, **kwargs) -> IO:
        return open(self.tempdir / path.lstrip('/'), *args, **kwargs)

    def render_chores(
        self,
        config: str,
        template: str,
        path: str,
        **render_kwargs
    ) -> None:
        sunday = week_sunday(get_current_date())
        current_offset = offset(sunday)
        chores = load_chores(config)

        choregroups = {
            choregroup: assign_chores(current_offset, chores, people)
            for choregroup, (chores, people) in chores.items()
        }
        render_kwargs['choregroups'] = choregroups
        render_kwargs['current_weekend_date'] = fmtdate(sunday)
        render_kwargs['current_offset'] = current_offset
        render_kwargs['chores_json'] = {
            group.id: ([chore.id for chore in chores], people)
            for group, (chores, people) in chores.items()
        }

        self.render_template(template, path, **render_kwargs)


@click.group()
def cli():
    """
    Generate chore.world
    """
    pass


@cli.command()
@click.option(
    '--output', '-o',
    help='Output directory',
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    required=True,
)
def generate(output: Path):
    """
    Generate chore.world
    """

    with Builder(output) as builder:
        builder.copy_dir(THISDIR / 'static', '/static')
        builder.copy_dir(THISDIR / 'assets', '/assets')
        builder.copy_dir(THISDIR / 'badges', '/badges')
        with builder.open('/CNAME', 'w') as f:
            f.write('chore.world\n')
        with builder.open('/.nojekyll', 'w'):
            pass

        builder.render_chores('chch.yaml', 'chch.jinja', '/',)
        builder.render_chores('welly.yaml', 'welly.jinja', '/welly')


def get_people(
    chores: dict[ChoreGroup, tuple[list[Chore], list[str]]]
) -> list[str]:
    all_people = []
    for _, people in chores.values():
        all_people.extend(people)
    return list(set(all_people))


@cli.command()
@click.option('--host', default='https://ntfy.sh')
@click.option('--output', '-o', type=click.File('w'), default='-')
@click.option('--indent', type=click.IntRange(min=0))
def ntfy_urls(host: str, output: IO, indent: Optional[int]):
    """
    Generate NTFY endpoints for each person
    """
    import json
    import uuid

    config_paths = ('chch.yaml', 'welly.yaml')
    path_people = {
        path: get_people(load_chores(path))
        for path in config_paths
    }

    endpoints = {
        path: {
            person: f'{host.rstrip("/")}/{uuid.uuid4()}'
            for person in people
        }
        for path, people in path_people.items()
    }

    output.write(json.dumps(endpoints, indent=indent or None) + '\n')


if __name__ == '__main__':
    cli()

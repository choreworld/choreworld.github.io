from __future__ import annotations

from contextlib import AbstractContextManager
import datetime
from pathlib import Path
import shutil
import tempfile
from typing import IO, Optional, Sequence, Union

import click
from dateutil import tz
import jinja2


THISDIR = Path(__file__).parent

TZINFO = tz.gettz('Pacific/Auckland')
START_WEEK = datetime.datetime(2021, 4, 11, tzinfo=TZINFO)


class Chore:
    id: str
    name: str

    def __init__(self, id: str, name: Optional[str] = None):
        self.id = id
        self.name = name or id.title()

    def __eq__(self, other) -> bool:
        return self.id == other.id and self.name == other.name

    def __hash__(self) -> int:
        return hash((self.id, self.name))


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
        chores: dict[str, tuple[Sequence[Chore], Sequence[str]]],
        template: str,
        path: str,
        **render_kwargs
    ) -> None:
        sunday = week_sunday(get_current_date())
        current_offset = offset(sunday)

        render_kwargs['choregroups'] = {
            choregroup: assign_chores(current_offset, chores, people)
            for choregroup, (chores, people) in chores.items()
        }
        render_kwargs['current_weekend_date'] = fmtdate(sunday)
        render_kwargs['current_offset'] = current_offset

        self.render_template(template, path, **render_kwargs)


@click.command()
@click.option(
    '--output', '-o',
    help='Output directory',
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    required=True,
)
def main(output: Path):
    """
    Generate chore.world
    """

    with Builder(output) as builder:
        builder.copy_dir(THISDIR / 'static', '/static')
        builder.copy_dir(THISDIR / 'assets', '/assets')
        builder.copy_dir(THISDIR / 'badges', '/badges')
        with builder.open('/CNAME', 'w') as f:
            f.write('chore.world\n')

        builder.render_chores(
            {
                'main': (
                    [
                        Chore('bins'),
                        Chore('kitchen'),
                        Chore('mop'),
                        Chore('toilet-lounge', 'Downstairs toilet and lounge'),
                        Chore('vacuum')
                    ],
                    ['Ashton', 'Dan', 'Harry', 'Sophie', 'Millie']
                ),
                'upstairs': (
                    [Chore('upstairs-bathroom', 'Upstairs bathroom')],
                    ['Dan', 'Harry', 'Sophie']
                ),
                'downstairs-bedroom': (
                    [Chore('ensuite')],
                    ['Millie', 'Ashton']
                )
            },
            'chch.jinja', '/',
            choregroup_names={
                'main': 'Whole flat',
                'upstairs': 'Upstairs',
                'downstairs-bedroom': 'Downstairs bedroom'
            }
        )

        builder.render_chores(
            {
                'main': (
                    [
                        Chore('bathroom'),
                        Chore('floors'),
                        Chore('misc')
                    ],
                    ['Emma', 'Charlotte', 'Nick']
                )
            },
            'welly.jinja', '/welly'
        )


if __name__ == '__main__':
    main()

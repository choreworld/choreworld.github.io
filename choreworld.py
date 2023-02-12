from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
import shutil
import tempfile
from typing import IO, Union

import click
import jinja2


THISDIR = Path(__file__).parent


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


def render_template(
    env: jinja2.Environment,
    template: str,
    **kwargs,
) -> None:
    pass


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
        builder.render_template('chch.jinja', '/')
        builder.render_template('welly.jinja', '/welly')


if __name__ == '__main__':
    main()

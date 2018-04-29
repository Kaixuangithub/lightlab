#!/usr/bin/env python
# -*- coding: utf-8 -*-

import distutils.cmd
import distutils.log
import subprocess
import os
import grp
import getpass
import sys
from setuptools import setup, find_packages


LABSTATE_FILENAME = "labstate.json"
JUPYTER_GROUP = "jupyter"

assert sys.version_info >= (3, 6), "Use python 3.6!"


def touch(fname, times=None):
    with open(fname, 'a'):
        os.utime(fname, times)


class PermissionCheckCommand(distutils.cmd.Command):
    """A custom command to create files for server installation."""

    description = 'Prepare files for server installation'
    user_options = [
        # The format is (long option, short option, description).
        ('jupyter-home-dir=', None, 'path to accessible jupyter home folder'),
        ('jupyter-group=', None, 'group name through which access jupyter folder'),
    ]

    def initialize_options(self):
        """Set default values for options."""
        # Each user option must be listed here with their default value.
        self.jupyter_home_dir = '/home/jupyter'
        self.jupyter_group = JUPYTER_GROUP

    def finalize_options(self):
        """Post-process options."""
        if self.jupyter_home_dir:
            self.need_permissions = False
            self.actions = []
            self.username = getpass.getuser()
            if self.username == "root":
                raise RuntimeError("root execution not supported")
            self.file_path = os.path.join(self.jupyter_home_dir, LABSTATE_FILENAME)

            if os.access(self.file_path, os.R_OK | os.W_OK | os.X_OK):
                return

            try:
                os.makedirs(self.jupyter_home_dir, mode=0o770, exist_ok=True)
            except PermissionError:
                self.need_permissions = True
                self.announce("Need to create {}.".format(self.jupyter_home_dir),
                              level=distutils.log.ERROR)
                self.actions.extend(["create_folder", "create_file"])
            else:
                try:
                    touch(self.file_path)
                except PermissionError:
                    self.need_permissions = True
                    self.announce("Need write permissions to {}.".format(self.file_path),
                                  level=distutils.log.ERROR)
                self.actions.append("create_file")

            if self.need_permissions:
                try:
                    gid = grp.getgrnam(self.jupyter_group).gr_gid
                    if not (gid in os.getgroups()):
                        self.actions.append("add_to_group")
                except KeyError:  # group not exist in getgrnam
                    self.actions.append("add_to_group")
                    self.actions.append("create_group")
                return

    def run(self):
        """Run command."""
        def run_command(self, command):
            self.announce("Running command: {}".format(command),
                          level=distutils.log.INFO)
            try:
                subprocess.check_call(command, shell=True)
            except subprocess.CalledProcessError:
                command = "sudo {}".format(command)
                self.announce("Running command: {}".format(command),
                              level=distutils.log.INFO)
                subprocess.check_call(command, shell=True)

        if not self.actions:
            self.announce("Permissions OK: Nothing to do.", level=distutils.log.INFO)
            return

        if "create_group" in self.actions:
            run_command(self, 'groupadd {}'.format(self.jupyter_group))

        if "add_to_group" in self.actions:
            run_command(self, 'usermod -a -G {} {}'.format(self.jupyter_group, self.username))
            self.announce("You must log out and login to take effect.", level=distutils.log.INFO)

        if "create_folder" in self.actions:
            run_command(self, 'mkdir -p -m 770 {}'.format(self.jupyter_home_dir))
            run_command(self, 'chown -R :{} {}'.format(self.jupyter_group, self.jupyter_home_dir))

        if "create_file" in self.actions:
            if not os.access(self.jupyter_home_dir, os.R_OK | os.X_OK):
                run_command(self, 'chmod 770 {}'.format(self.jupyter_home_dir))
            run_command(self, 'touch {}'.format(self.file_path))
            run_command(self, 'chmod 770 {}'.format(self.file_path))
            run_command(self, 'chown -R :{} {}'.format(self.jupyter_group, self.file_path))


def main():
    with open('README.md') as f:
        readme = f.read()

    with open('LICENSE') as f:
        license = f.read()

    with open("version.py") as f:
        code = compile(f.read(), "version.py", 'exec')
        version_dict = {}
        exec(code, {}, version_dict)
        version = version_dict['version']

    metadata = dict(
        name='lightlab',
        version=version,
        description='Lightwave Lab instrument automation tools',
        long_description=readme,
        license=license,
        packages=find_packages(exclude=('tests', 'docs', 'data')),
        install_requires=[
            'dpath',
            'jsonpickle',
            'matplotlib',
            'IPython',
            'PyVISA',
            'scipy',
            'sklearn',
            'dill',
        ],
        cmdclass={
            "server_permissions": PermissionCheckCommand,
        },
    )

    setup(**metadata)


if __name__ == '__main__':
    main()

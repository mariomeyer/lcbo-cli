from importlib.metadata import distribution


def test_installed_distribution_provides_lcbo_command():
    """The PyPI distribution must expose the documented lcbo executable."""
    package = distribution("lcbo")
    commands = {entry.name: entry.value for entry in package.entry_points
                if entry.group == "console_scripts"}
    assert commands["lcbo"] == "lcbo_cli.cli:main"

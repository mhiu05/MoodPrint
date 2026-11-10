def test_packages_import_without_path_hacks():
    import app
    import moodprint_agent
    import moodprint_shared

    assert moodprint_shared.__package__ == "moodprint_shared"
    assert moodprint_agent.__package__ == "moodprint_agent"
    assert app.__package__ == "app"

def test_packages_import_without_path_hacks():
    import app
    import safevoice_agent
    import safevoice_shared

    assert safevoice_shared.__package__ == "safevoice_shared"
    assert safevoice_agent.__package__ == "safevoice_agent"
    assert app.__package__ == "app"

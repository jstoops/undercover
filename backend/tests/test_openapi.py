from backend.main import app

METHODS = {"get", "post", "put", "patch", "delete"}


def operations():
    schema = app.openapi()
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            if method in METHODS:
                yield f"{method.upper()} {path}", operation, schema


def body_schema(operation, schema):
    ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    return schema["components"]["schemas"][ref.split("/")[-1]]


def test_every_operation_has_an_id_and_a_one_line_docstring():
    for name, operation, _ in operations():
        assert operation.get("operationId"), name
        description = operation.get("description", "")
        assert description, name
        assert "\n" not in description.strip(), name


def test_no_operation_has_optional_inputs():
    for name, operation, schema in operations():
        for parameter in operation.get("parameters", []):
            assert parameter["required"], f"{name} {parameter['name']}"
        if "requestBody" in operation:
            assert operation["requestBody"]["required"], name
            body = body_schema(operation, schema)
            assert set(body.get("required", [])) == set(body["properties"]), name

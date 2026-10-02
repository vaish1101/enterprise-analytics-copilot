from scripts.public_release_check import findings

def test_extra_secret_categories_do_not_expose_values():
    inputs = {
        'bearer_literal': b'Bearer ' + b'a' * 30,
        'private_runtime_path': b'/pri' + b'vate/tmp/private-runtime.txt',
        'personal_email': b'private.person' + b'@example.test',
        'credential_url': b'redis://' + b'example-user:example-password' + b'@' + b'cache.invalid',
        'credential_assignment': b'api_key=' + b'"' + b'x' * 30 + b'"',
    }
    for category, value in inputs.items():
        result = findings('config/unsafe.txt', value)
        assert category in {item['category'] for item in result}
        assert value.decode() not in repr(result)

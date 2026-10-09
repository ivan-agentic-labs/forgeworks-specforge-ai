"""Existing business acceptance flow through the external object provider."""
from test_specforge_flow import test_requirement_to_approved_spec as acceptance_flow
from specforge_ai.infrastructure.object_storage import ObjectStorage


def test_business_flow_uses_external_objects(tmp_path,monkeypatch):
    for key,value in {"S3_ENDPOINT":"https://storage.example.invalid","S3_BUCKET":"private-bucket","S3_ACCESS_KEY_ID":"synthetic-access","S3_SECRET_ACCESS_KEY":"synthetic-secret"}.items():
        monkeypatch.setenv(key,value)
    objects={}
    def transfer(self,method,key,body=None):
        if method=="PUT":objects[key]=body;return b""
        return objects[key]
    monkeypatch.setattr(ObjectStorage,"transfer",transfer)
    acceptance_flow(tmp_path)
    assert objects and all(key.startswith("specforge-ai/") for key in objects)
    assert not (tmp_path/"artifacts/objects.sqlite").exists()

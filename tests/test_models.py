# coding=utf-8
"""Unit tests for models.py."""
from app import app
from models import MagicKey, Response
from . import testutil


class MagicKeyTest(testutil.TestCase):

    def setUp(self):
        super(MagicKeyTest, self).setUp()
        self.key = MagicKey.get_or_create('y.z')

    def test_magic_key_get_or_create(self):
        assert self.key.mod
        assert self.key.public_exponent
        assert self.key.private_exponent

        same = MagicKey.get_or_create('y.z')
        self.assertEqual(same, self.key)

    def test_href(self):
        href = self.key.href()
        self.assertTrue(href.startswith('data:application/magic-public-key,RSA.'), href)
        self.assertIn(self.key.mod, href)
        self.assertIn(self.key.public_exponent, href)

    def test_public_pem(self):
        pem = self.key.public_pem()
        self.assertTrue(pem.decode().startswith('-----BEGIN PUBLIC KEY-----\n'), pem)
        self.assertTrue(pem.decode().endswith('-----END PUBLIC KEY-----'), pem)

    def test_private_pem(self):
        pem = self.key.private_pem()
        self.assertTrue(pem.decode().startswith('-----BEGIN RSA PRIVATE KEY-----\n'), pem)
        self.assertTrue(pem.decode().endswith('-----END RSA PRIVATE KEY-----'), pem)


class ResponseTest(testutil.TestCase):

    def test_constructor(self):
        resp = Response('abc', 'xyz')
        self.assertEqual('abc xyz', resp.key.id())

        resp = Response('abc#1', 'xyz#Z')
        self.assertEqual('abc__1 xyz__Z', resp.key.id())

    def test_get_or_create(self):
        resp = Response.get_or_create('abc', 'xyz')
        self.assertEqual('abc xyz', resp.key.id())

        resp = Response.get_or_create('abc#1', 'xyz#Z')
        self.assertEqual('abc__1 xyz__Z', resp.key.id())

    def test_proxy_url(self):
        with app.test_request_context('/'):
            resp = Response.get_or_create('abc', 'xyz')
            self.assertIsNone(resp.proxy_url())

            resp.source_as2 = 'as2'
            self.assertEqual('http://localhost/render?source=abc%26target=xyz',
                             resp.proxy_url())

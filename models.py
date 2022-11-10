"""Datastore model classes."""
import logging
import urllib.parse

from Crypto.PublicKey import RSA
from django_salmon import magicsigs
from flask import request
from google.cloud import ndb
from oauth_dropins.webutil.models import StringIdModel

logger = logging.getLogger(__name__)


class MagicKey(StringIdModel):
    """Stores a user's public/private key pair used for Magic Signatures.

    The key name is the domain.

    The modulus and exponent properties are all encoded as base64url (ie URL-safe
    base64) strings as described in RFC 4648 and section 5.1 of the Magic
    Signatures spec.

    Magic Signatures are used to sign Salmon slaps. Details:
    http://salmon-protocol.googlecode.com/svn/trunk/draft-panzer-magicsig-01.html
    http://salmon-protocol.googlecode.com/svn/trunk/draft-panzer-salmon-00.html
    """
    mod = ndb.StringProperty(required=True)
    public_exponent = ndb.StringProperty(required=True)
    private_exponent = ndb.StringProperty(required=True)

    @staticmethod
    @ndb.transactional()
    def get_or_create(domain):
        """Loads and returns a MagicKey. Creates it if necessary."""
        key = MagicKey.get_by_id(domain)

        if not key:
            # this uses urandom(), and does nontrivial math, so it can take a
            # while depending on the amount of randomness available.
            pubexp, mod, privexp = magicsigs.generate()
            key = MagicKey(id=domain, mod=mod, public_exponent=pubexp,
                           private_exponent=privexp)
            key.put()

        return key

    def href(self):
        return 'data:application/magic-public-key,RSA.%s.%s' % (
            self.mod, self.public_exponent)

    def public_pem(self):
        """Returns: bytes"""
        rsa = RSA.construct((magicsigs.base64_to_long(str(self.mod)),
                             magicsigs.base64_to_long(str(self.public_exponent))))
        return rsa.exportKey(format='PEM')

    def private_pem(self):
        """Returns: bytes"""
        rsa = RSA.construct((magicsigs.base64_to_long(str(self.mod)),
                             magicsigs.base64_to_long(str(self.public_exponent)),
                             magicsigs.base64_to_long(str(self.private_exponent))))
        return rsa.exportKey(format='PEM')


class Response(StringIdModel):
    """A reply, like, repost, or other interaction that we've relayed.

    Key name is 'SOURCE_URL TARGET_URL', e.g. 'http://a/reply http://orig/post'.
    """
    STATUSES = ('new', 'complete', 'error', 'ignored')
    PROTOCOLS = ('activitypub', 'ostatus')
    DIRECTIONS = ('out', 'in')

    domain = ndb.StringProperty()
    status = ndb.StringProperty(choices=STATUSES, default='new')
    protocol = ndb.StringProperty(choices=PROTOCOLS)
    direction = ndb.StringProperty(choices=DIRECTIONS)

    # usually only one of these at most will be populated.
    source_mf2 = ndb.TextProperty()  # JSON
    source_as2 = ndb.TextProperty()  # JSON
    source_atom = ndb.TextProperty()

    target_as2 = ndb.TextProperty()  # JSON

    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    def __init__(self, source=None, target=None, **kwargs):
        if source and target:
            assert 'id' not in kwargs
            kwargs['id'] = self._id(source, target)
            logger.info(f"Response id (source target): {kwargs['id']}")
        super(Response, self).__init__(**kwargs)

    @classmethod
    def get_or_create(cls, source=None, target=None, **kwargs):
        logger.info(f'Response source target: {source} {target}')
        return cls.get_or_insert(cls._id(source, target), **kwargs)

    def source(self):
        return self.key.id().split()[0]

    def target(self):
        return self.key.id().split()[1]

    def proxy_url(self):
        """Returns the Bridgy Fed proxy URL to render this response as HTML."""
        if self.source_mf2 or self.source_as2 or self.source_atom:
            source, target = self.key.id().split(' ')
            # via https://stackoverflow.com/questions/2506379/add-params-to-given-url-in-python
            url = f'{request.host_url}render'
            params = {
                    'source': source,
                    'target': target,
                    }

            url_parts = list(parse.urlparse(url))
            query = dict(parse.parse_qsl(url_parts[4]))
            query.update(params)

            url_parts[4] = urlencode(query)

            return urlparse.urlunparse(url_parts)

    @classmethod
    def _id(cls, source, target):
        assert source
        assert target
        return '%s %s' % (cls._encode(source), cls._encode(target))

    @classmethod
    def _encode(cls, val):
        return val.replace('#', '__')

    @classmethod
    def _decode(cls, val):
        return val.replace('__', '#')


class Follower(StringIdModel):
    """A follower of a Bridgy Fed user.

    Key name is 'USER_DOMAIN FOLLOWER_ID', e.g.:
      'snarfed.org https://mastodon.social/@swentel'.
    """
    STATUSES = ('active', 'inactive')

    # most recent AP Follow activity (JSON). must have a composite actor object
    # with an inbox, publicInbox, or sharedInbox!
    last_follow = ndb.TextProperty()
    status = ndb.StringProperty(choices=STATUSES, default='active')

    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    @classmethod
    def _id(cls, user_domain, follower_id):
        assert user_domain
        assert follower_id
        return '%s %s' % (user_domain, follower_id)

    @classmethod
    def get_or_create(cls, user_domain, follower_id, **kwargs):
        logger.info(f'new Follower for {user_domain} {follower_id}')
        return cls.get_or_insert(cls._id(user_domain, follower_id), **kwargs)


BASE_METADATA_FIELDS = ['title', 'description', 'author', 'language', 'license', 'content-type', 'sources']
OPTIONAL_METADATA_FIELDS = ['thumbnail', 'preview', 'fee', 'contact', 'pubkey']

#v0.0.1 metadata
METADATA_REVISIONS = {'0.0.1': {'required': BASE_METADATA_FIELDS, 'optional': OPTIONAL_METADATA_FIELDS}}

#v0.0.2 metadata additions
METADATA_REVISIONS['0.0.2'] = {'required': ['nsfw'], 'optional': []}
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from ..model import ModelView, ModelSQL, ModelStorage, fields
from ..pool import Pool
from ..cache import Cache

class SafeURLs(ModelSQL, ModelView):
    "SafeURLs"
    _name = 'safe.urls'
    _description = __doc__
    url = fields.Char('URL', required=True)

    def __init__(self):
        super(SafeURLs, self).__init__()
        self._rpc.update({
            'checkURL': False,
        })

    @Cache('safe_urls.checkURL')
    def checkURL(self, url):
        pool = Pool()
        urls_obj = pool.get('safe.urls')
        """
        url = urls_obj.search([
                ('url', '=', url),
                ])
        """
        return urls_obj
    
SafeURLs()
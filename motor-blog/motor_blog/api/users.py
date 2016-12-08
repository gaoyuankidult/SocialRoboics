from motor_blog.api import rpc
from tornado.options import options as opts


class Users(object):
    """Mixin for motor_blog.api.handlers.APIHandler, deals with XML-RPC calls
       related to users
    """
    @rpc
    def blogger_getUsersBlogs(self, blog_id, user, password):
        # Mocked to always return the user as admin
        doc = {
            'blogid': "1",
            'blogName': opts.blog_name,
            'url': "",
            'xmlrpc': "",
            'isAdmin': True
        }

        self.result([doc])

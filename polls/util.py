import base64

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from tastypie.authentication import MultiAuthentication
from tastypie.authorization import DjangoAuthorization


def get_client_ip(request):
    """
    get client ip
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[-1].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user(request, clientid=None):
    """
    get a valid user, get or create a user by IP address 

    if the user is anonmyous:
        this will get or create a user with the given clientid. if the clientid is
        not specified it defaults to the ip address 
        (i.e. no django credentials)
        returns the user

    if the user is authenticated:
        returns it unchanged
    """
    user = request.user
    if request.user.is_anonymous():
        User = get_user_model()
        username = clientid or get_client_ip(request)
        try:
            user = User.objects.get(username=username)
        except:
            unusable_password = make_password(None)
            user = User.objects.create_user(username,
                                            email=settings.DEFAULT_FROM_EMAIL,
                                            password=unusable_password)
    return user


class ReasonableDjangoAuthorization(DjangoAuthorization):

    """
    grant read access based on given read_list and read_detail permissions

    Usage:
        # set permission to None to allow public access (no permission checks)
        permissions = {
          'read_list' : 'change',  
          'read_detail' : 'view'
        }
        authorization = ReasonableDjangoAuthorization(**permissions)

    Rationale: 
        by default, tastypie > 0.13 requires the 'change' permission for
        any user to GET list or detail, which doesn't make sense in an API
        context. see https://github.com/django-tastypie/django-tastypie/issues/1407
    """
    def __init__(self, read_list='change',
                 read_detail='view'):
        self.perm_read_list = read_list
        self.perm_read_detail = read_detail

    def read_detail(self, object_list, bundle):
        if self.perm_read_detail:
            return self.perm_obj_checks(bundle.request, self.perm_read_detail, bundle.obj)
        else:
            return True

    def read_list(self, object_list, bundle):
        if self.perm_read_list:
            return self.perm_list_checks(bundle.request, self.perm_read_list, object_list)
        else:
            return object_list


class IPAuthentication(MultiAuthentication):

    """
    an authentication scheme that automatically gets or creates a user based
    on the remote ip address if the user cannot be authenticated otherwise. 

    works across proxies. if the client provides
    a 'quickpollscid' cookie also works for users behind NATs or enterprise
    proxies. note that the cookie value is base64 encoded assuming we get
    a UUID of some sorts to ensure we get valid usernames. 

    Usage:
        # use the same as MultiAuthentication()
        IPAuthentication(BasicAuthentication(), SessionAuthentication())
    """
    def is_authenticated(self, request, **kwargs):
        authed = super(IPAuthentication, self).is_authenticated(
            request, **kwargs)
        if not authed or request.user.is_anonymous():
            # base64 encode to get uuid's below 30 chars (max length of
            # username)
            clientid = request.COOKIES.get('quickpollscid', None)
            if clientid:
                clientid = base64.b64encode(clientid)
            request.user = get_user(request, clientid=clientid)
        return authed

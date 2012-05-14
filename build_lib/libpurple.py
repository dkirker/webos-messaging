from os.path import join
from glob import glob
from util import ant_glob
from itertools import chain
from re import match

from waflib.Configure import conf

def get_path_and_version():
    try:
        path = glob("deps/pidgin-*/libpurple")[-1]
        version = match("deps/pidgin-(?P<version>[^/]*)/libpurple", path).groups()[0]
        return (path, version)
    except IndexError:
        raise RuntimeError("Couldn't find libpurple sources")

def get_path():
    return get_path_and_version()[0]

def build_protocol(ctx, name, path=None, exclude=[], use=[]):
    root_path = join(ctx.env.PURPLE_PATH, "protocols", path if path else name)
    ctx.objects(target="protocol_%s" % name,
                source=ant_glob(ctx, root_path, "**", "*.c", exclude=exclude),
                includes=root_path,
                use=" ".join(["GLIB XML PURPLE_BUILD"] + use)
               )

def configure(conf):
    conf.load('compiler_c intltool')

    path, version = get_path_and_version()
    conf.env.PURPLE_PATH = path
    conf.env.PURPLE_VERSION = version

    if conf.env.PURPLE_SSL:
        # Order matters: It seems like ssl-gnutls has to be loaded before
        # core-ssl to be found (see ssl.c:probe_ssl_plugins)
        conf.env.PURPLE_PLUGINS += ["ssl-" + conf.env.PURPLE_SSL, "ssl"]

        conf.env.append_value("LIB_PURPLE_BUILD", ["gnutls"])

    plugins = conf.env.PURPLE_PLUGINS
    protocols = conf.env.PURPLE_PROTOCOLS

    if "jabber" in protocols:
        conf.env.PURPLE_SASL = True
        conf.load('sasl', tooldir='build_lib')
    else:
        conf.env.PURPLE_SASL = False

    conf.check_cfg(atleast_pkgconfig_version='0.1')
    conf.check_cfg(package='libxml-2.0', uselib_store='XML',
                   args=['--cflags', '--libs'])

    conf.env.append_value("DEFINES_PURPLE_BUILD", ["HAVE_CONFIG_H"])
    conf.env.append_value("INCLUDES_PURPLE_BUILD", ["libpurple_config", path])
    conf.env.append_value("LIB_PURPLE_BUILD", ["resolv"])

    # We are going to build a shared library
    conf.env.append_value("CFLAGS_PURPLE_BUILD", ["-fPIC"])

    headers = ["arpa/nameser_compat", "fcntl", "sys/time",
               "unistd", "locale", "libintl", "signal", "stdint", "regex"]

    for i in headers:
        conf.check_cc(header_name=i + ".h", mandatory=False,
                      auto_add_header_name=True)

    conf.define("PURPLE_STATIC_PRPL", 1)
    conf.define("PURPLE_PLUGINS", 1)
    conf.define("HAVE_GETIFADDRS", 1)
    conf.define("HAVE_INET_NTOP", 1)
    conf.define("HAVE_INET_ATON", 1)
    conf.define("HAVE_GETADDRINFO", 1)
    conf.define("HAVE_STRUCT_TM_TM_ZONE", 1)
    conf.define("HAVE_TM_GMTOFF", 1)
    conf.define("HAVE_TIMEZONE", 1)
    conf.define("HAVE_TIMGM", 1)
    conf.define("HAVE_STRFTIME_Z_FORMAT", 1)
    conf.define("HAVE_FILENO", 1)
    conf.define("HAVE_STRUCT_SOCKADDR_SA_LEN", 1)
    conf.define("VERSION", conf.env.PURPLE_VERSION)
    conf.define("DISPLAY_VERSION", conf.env.PURPLE_VERSION)
    conf.define("DATADIR", ".")
    conf.define("SYSCONFDIR", ".")
    conf.define("PACKAGE_NAME", "libpurple")
    conf.define("HAVE_SSL", 1)
    conf.define("HAVE_ICONV", 1)
    conf.define("LIBDIR", ".")
    conf.define("SIZEOF_TIME_T", 4, quote=False)
    conf.define("HAVE_CONFIG_H", 1, quote=False)
    conf.define("HAVE_CYRUS_SASL", 1, quote=False)
    conf.define("HAVE_GNUTLS_PRIORITY_FUNCS", 1)
    conf.define("_GNU_SOURCE", 1, quote=False)

    conf.define("SSL_CERTIFICATES_DIR",
            join(conf.env.APP_PATH, "share", "ca-certs")
    )

    conf.define("ENABLE_NLS", 1, quote=False)
    conf.define("PACKAGE", "libpurple")
    conf.define("LOCALEDIR",
                join(conf.env.APP_PATH, "share", "locale")
    )

    proto_extern = "\\\n".join(
                        "extern gboolean purple_init_%s_plugin();" %
                            name.replace('-', '_')
                        for name in chain(plugins, protocols)
                        )

    proto_func = "\\\n".join(
                        "   purple_init_%s_plugin();" % name.replace('-', '_')
                        for name in chain(plugins, protocols)
                        )

    proto_init = """%s\\
void static_proto_init()\\
{\\
%s\\
}""" % (proto_extern, proto_func)

    conf.define("STATIC_PROTO_INIT", proto_init, quote=False)

    conf.write_config_header('libpurple_config/config.h')


def build(bld):
    use = ["BASE", "GLIB", "XML", "GNUTLS", "PURPLE_BUILD"]

    for i in bld.env.PURPLE_PROTOCOLS:
        exclude = ["win32"]
        path = None
        if i == "jabber":
            bld.load("sasl", tooldir="build_lib")
            use += ["sasl", "SASL_BUILD"]
        if i == "icq":
            exclude += ["libaim.c"]
            path = "oscar"
        if i == "aim":
            exclude += ["libicq.c"]
            path = "oscar"

        build_protocol(bld, i, path, exclude=exclude, use=use)
        use += ["protocol_%s" % i]

    a = bld.objects(target="plugins",
                source=[join(bld.env.PURPLE_PATH, "plugins",
                            (join("ssl", i) if i.startswith("ssl") else
                                i.lower())
                            + ".c"
                            )
                        for i in bld.env.PURPLE_PLUGINS
                       ],
                use=use)

    exclude = ["purple-client.c",
               "purple-client-example.c",
               "nullclient.c",
               "dbus-server.c",
               "protocols",
               "plugins",
               "win32",
               "tests"]

    path = bld.env.PURPLE_PATH

    bld.shlib(
                target="purple",
                source=ant_glob(bld, path, "**", "*.c", exclude=exclude),
                export_includes=path,
                includes=path,
                use=use + ["plugins"],
             )

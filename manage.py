import eventlet

eventlet.monkey_patch()

from flask_script import Manager, Server as _Server, Option
from captionthis import create_app, socketio


app = create_app()
manager = Manager(app)


# From https://github.com/miguelgrinberg/flack/blob/master/manage.py#L16
class Server(_Server):
    help = description = "Runs the Socket.IO web server"

    def get_options(self):
        options = (
            Option("-h", "--host", dest="host", default=self.host),
            Option("-p", "--port", dest="port", type=int, default=self.port),
            Option(
                "-d",
                "--debug",
                action="store_true",
                dest="use_debugger",
                help=("enable the Werkzeug debugger (DO NOT use in production code)"),
                default=self.use_debugger,
            ),
            Option(
                "-D",
                "--no-debug",
                action="store_false",
                dest="use_debugger",
                help="disable the Werkzeug debugger",
                default=self.use_debugger,
            ),
            Option(
                "-r",
                "--reload",
                action="store_true",
                dest="use_reloader",
                help=(
                    "monitor Python files for changes (not 100%% safe for production use)"
                ),
                default=self.use_reloader,
            ),
            Option(
                "-R",
                "--no-reload",
                action="store_false",
                dest="use_reloader",
                help="do not monitor Python files for changes",
                default=self.use_reloader,
            ),
        )
        return options

    def __call__(self, app, host, port, use_debugger, use_reloader):
        # override the default runserver command to start a Socket.IO server
        if use_debugger is None:
            use_debugger = app.debug

            if use_debugger is None:
                use_debugger = True

        if use_reloader is None:
            use_reloader = app.debug

        socketio.run(
            app,
            host=host,
            port=port,
            debug=use_debugger,
            use_reloader=use_reloader,
            **self.server_options,
        )


manager.add_command("run", Server())


@manager.command
def test():
    pass


if __name__ == "__main__":
    manager.run()

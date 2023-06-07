from webserver import app

if __name__ == "__main__":
    app.run()
    app.config['SERVER_NAME'] = 'toldcard.com'

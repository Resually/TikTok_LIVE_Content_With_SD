from flask import Flask, send_file

app = Flask(__name__)

@app.route('/')
def index():
    return '''
        <html style="background-color:#000000">
            <body>
                <img src="/image" id="live-image" alt="Live Image" style="display: block; margin-left:auto; margin-right: auto;width: %50;">
                <script>
                    setInterval(function(){
                        var img = document.getElementById('live-image');
                        img.src = '/image?' + new Date().getTime();
                    }, 5000); // Refresh every 5 seconds
                </script>
            </body>
        </html>
    '''

@app.route('/image')
def image():
    return send_file('output.png', mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True)

from flask import Blueprint, render_template


main = Blueprint('main', __name__)


@main.route('/', methods=['GET'])
def index():
    return render_template('index.html')


#@main.route('/test', methods=['GET'])
#def run_tests():
#    if TEST:
#        return render_template('t/pod_index.html')
#    return "not found", 404

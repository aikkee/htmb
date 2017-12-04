import os
import json

from flask import Flask, render_template, redirect, session, url_for, \
                  request, make_response, send_from_directory, abort, flash
from flask.ext import excel
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_
import datetime
from datetime import date
from flask.ext.wtf import Form
from wtforms import StringField, SelectField, HiddenField, validators

application = Flask(__name__)
application.config.from_pyfile('bookings.cfg')
db = SQLAlchemy(application)

# -- Forms --
class BookingForm(Form):
    location = SelectField('location')
    date_time = SelectField('date_time')
    booking_ref = HiddenField('booking_ref')
    expire_on = HiddenField('expire_on')

# -- Models --
class Triage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(10))
    description = db.Column(db.String(20))
    capacity = db.Column(db.Integer)
    available = db.Column(db.Integer)

    def __repr__(self):
        return '<Triage %r, %r, %r, %r>' % (self.location, self.description, \
            self.capacity, self.available)

class Reference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.String(10), unique=True) # Cross reference back to EITP in future
    booking_ref = db.Column(db.String(10), unique=True) # Randomised id that is not in sequence like case_id
    expire_on = db.Column(db.DateTime)
    triage_id = db.Column(db.Integer, db.ForeignKey('triage.id'))
    update_on = db.Column(db.DateTime)

    def __repr__(self):
        return '<Reference %r, %r>' % (self.booking_ref, self.expire_on)



# -- Views --
@application.route('/')
@application.route('/index')
def index():
    return render_template('index.html')

@application.route('/init')
def init():
    ref = request.args.get('ref')
    isnew = request.args.get('isnew')
    # also use this as the indicator for where the request comes from
    if isnew is None or isnew=='':
        isnew='yes'

    if (isValidReference(ref) == False):
        return redirect(url_for('index'))

    if ref is None or ref == '':
        return redirect(url_for('index'))

    # TODO: Improve the query later by combining the 2 statements
    reference = Reference.query.filter(Reference.booking_ref==ref).first()
    booked_triage = Triage.query.filter(Triage.id==reference.triage_id).first()
    # Need to also handle cases where user use the same link to amend booking
    # When initiated from user through the sms link, isnew will be 'yes'
    # When initiated from change_booking page, isnew will be 'no'
    if isnew=='yes' and booked_triage!=None:
        m = {'location':booked_triage.location, \
              'date_time':booked_triage.description}
        b = [{'ref':ref, 'isnew':'no', 'label':'Yes'}]
        return render_template('change_booking.html', message=m, buttons=b)

    # obtain the triage slots from database
    # available_triages = Triage.query.filter(Triage.available>0)
    bookingForm = BookingForm()
    # bookingForm.date_time.choices = [('', 'Choose Date & Time')] + [ (t.id, t.description) for t in available_triages]
    bookingForm.date_time.choices = [('', 'Choose Date & Time')]

    # obtain locations of available slots
    triages = Triage.query.filter(Triage.available>0)
    locations = list(set([(t.location) for t in triages if show_for_booking(t, str(reference.expire_on))]))
    bookingForm.location.choices = [('', 'Choose Location')] + [
        (l, l) for l in locations]
    
    bookingForm.booking_ref.data = ref
    if reference != None:
        bookingForm.expire_on.data = reference.expire_on
    return render_template('book_htmb_form.html', form=bookingForm, isnew='yes')

@application.route('/save', methods=['POST'])
def save():

    if request.form.get('date_time')=="":
        flash('Both fields are required.')
        return redirect(redirect_url())

    b_ref = request.form.get('booking_ref')
    tid = request.form.get('date_time', type=int)

    reference = Reference.query.filter(Reference.booking_ref==b_ref).first()
    # Release booking slot
    if reference.triage_id is not None:
        booked_triage = Triage.query.filter(Triage.id==reference.triage_id).first()
        if booked_triage is not None:
            booked_triage.available = booked_triage.available + 1 
            application.logger.info('Return slot for Triage ID: %r' % booked_triage.id)
            db.session.commit()

    triage = Triage.query.filter(Triage.id==tid).first()
    if triage.available == 0:
        # Fully booked, cannot accept anymore
        m = {'location':triage.location, \
              'date_time':triage.description}
        b = [{'ref':b_ref, 'label':'OK'}]
        return render_template('fully_booked.html', message=m, buttons=b)
    else:
        # update new booking
        reference.triage_id = tid
        reference.update_on = datetime.datetime.now()
            
        triage.available = triage.available - 1 

        application.logger.info('Draw down from Triage ID: %s for Reference ID: %s' % (tid, reference.id))

        db.session.commit()
        flash('Thank you for your submission.  Your session on %s at %s is confirmed.' %
                (triage.description, triage.location))
        return render_template('acknowledge.html')


def redirect_url(default='index'):
    return request.args.get('next') or \
           request.referrer or \
           url_for(default)

def show_for_booking(triage, exp, location=None):
    # handle reference expiry date
    exp_date = date( int(exp[:4]), int(exp[5:7]), int(exp[8:10]) )
    earliest_date = exp_date + datetime.timedelta(days=3)
    # change triage description to date object
    triage_date = datetime.datetime.strptime(triage.description[:11], '%d %b %Y').date()

    return triage.location == location and triage.available > 0 and triage_date > earliest_date

@application.route("/slotsfor/<location>/", methods=["GET", "POST"])
def get_slots(location):
    triages = Triage.query.all()
    ref_expiry = request.args['expire_on']
    data = [
        (t.id, t.description) for t in triages if show_for_booking(t, ref_expiry, location) 
    ]
    response = make_response(json.dumps(data))
    response.content_type = 'application/json'
    return response


def isValidReference(booking_ref):
    bRef = Reference.query.filter(and_(Reference.booking_ref==booking_ref,
                                       Reference.expire_on>datetime.datetime.now())).first()
    if (bRef != None):
        return True
    else:
        flash('Invalid reference <%s>. Please contact HRSS.' % booking_ref)
        return False

@application.route('/admin/check_slots')
def check_slots():
    return render_template('show_slots.html', slots=Triage.query.all())

@application.route("/admin/add_case", methods=['GET', 'POST'])
def add_case():
    # handle submission
    if request.method == 'POST':
        ref = request.form.get('ref')
        expiry = request.form.get('expiry')
        r = create_new_reference(ref, expiry)
        flash('%s activated. Expires on %s.' \
                % (r.booking_ref, r.expire_on.strftime('%d-%b-%Y')))
        return render_template('add_case.html')

    return render_template('add_case.html')

def create_new_reference(ref, expiry):
    r = Reference()
    r.case_id = 'ADMIN'
    r.booking_ref = ref 
    expiry_str = expiry + " 16:00:00" #handle timezone of server - 8 hrs behind us
    r.expire_on = datetime.datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
    db.session.add(r)
    db.session.commit()
    return r

@application.route("/admin/import_case", methods=['GET', 'POST'])
def import_case():
    if request.method == 'POST':
        def ref_init_func(row):
            r = Reference()
            r.case_id = row['CASE_ID']
            r.booking_ref = row['BOOKING_REF']
            r.expire_on = datetime.datetime.strptime(row['EXPIRE_ON'], \
                "%Y-%m-%d %H:%M:%S")
            return r
        request.save_book_to_database(field_name='file', session=db.session, \
                                      tables=[Reference], \
                                      initializers=([ref_init_func]))
        flash('HTMB cases created')
        return render_template('acknowledge.html')
    return render_template('import.html', title='Import HTMB Referrals')

@application.route("/admin/import_slot", methods=['GET', 'POST'])
def import_slot():
    if request.method == 'POST':
        def triage_init_func(row):
            t = Triage()
            t.location = row['LOCATION']
            t.description = row['DESCRIPTION']
            t.capacity = row['CAPACITY']
            t.available = row['CAPACITY']
            return t
        request.save_book_to_database(field_name='file', session=db.session, \
                                      tables=[Triage], \
                                      initializers=([triage_init_func]))
        flash('HTMB timeslot created')
        return render_template('acknowledge.html')
    return render_template('import.html', title='Import HTMB Timeslot')

@application.route("/admin/export_booking", methods=['GET'])
def doexport():

    col = ['case_id', 'booking_ref','description', 'update_on', 'location']
    qs = Reference.query.join(Triage, Reference.triage_id == Triage.id).add_columns( \
            Reference.case_id, Reference.booking_ref, Triage.description, \
            Reference.update_on, Triage.location).filter( \
                Reference.triage_id != None)
    # qs = Triage.query.filter(Triage.booking_ref != None)
    return excel.make_response_from_query_sets(qs, col, "csv")

@application.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

#----------test codes----------------------
@application.route('/<path:resource>')
def serveStaticResource(resource):
    return send_from_directory('static/', resource)

@application.route("/test")
def test():
    user_agent = request.headers.get('User-Agent')
    return "<p>It's Alive!<br/>Your browser is %s</p>" % user_agent

#----------main codes----------------------
if __name__ == '__main__':
    application.run()

 

from django.db import models
from django.utils.translation import ugettext_lazy as _
from datetime import datetime
from django.contrib.localflavor.us.models import PhoneNumberField
from myutils.models import MarkupMixin

from django.contrib.auth.models import User
from django_extensions.db.models import TimeStampedModel, TitleSlugDescriptionModel
from committees.managers import BoardManager, ActiveTermManager, ActiveGroupManager
from schedule.models import Event
from simple_history.models import HistoricalRecords

class GroupType(TitleSlugDescriptionModel):
    '''Group type model.

    Allows catering the group type to how orgs are organized into governing groups.
    
    e.g. Governing board, Ad-hoc committee, Congregation'''
    order = models.IntegerField(_('Order'), max_length=2)

    class Meta:
        verbose_name = _('Group type')
        verbose_name_plural = _('Group types')
        ordering = ('order', 'title',)

    def __unicode__(self):
        return self.title

    @models.permalink
    def get_absolute_url(self):
        return ('cm-group-type-detail', None, {'slug': self.slug})


class Group(TimeStampedModel, TitleSlugDescriptionModel):
    '''Group model.

    Manages the various types of governing groups in an organization. (e.g. Governing Board, Music Committee, etc...)
    '''

    order=models.IntegerField(_('Order'), max_length=2, help_text='Used to order groups in a list. Set all ranks the same to sort by alpha.')
    type=models.ForeignKey(GroupType)
    active=models.BooleanField(_('Active'), default=True)
    formed_on=models.DateField(_('Formed on'), blank=True, null=True)
    disbanded_on=models.DateField(_('Disbanded on'), blank=True, null=True)
    adhoc=models.BooleanField(_('Ad-hoc'), default=False, help_text='Is this is an ad-hoc group?')
    members=models.ManyToManyField('Person', related_name='members', blank=True, null=True, help_text='Non-term limited members of the group.')
    past_members=models.ManyToManyField('Person', related_name='past_members', blank=True, null=True, help_text='Non-term limited members who have left the group')
    deceased_members = models.ManyToManyField('Person', related_name='deceased_members', blank=True, null=True, help_text='Non-term limited members who have passed away')

    objects=models.Manager()
    active_objects=ActiveGroupManager()

    class Meta:
        verbose_name = _('Group')
        verbose_name_plural = _('Groups')

    def __unicode__(self):
        return u'%s %s' % (self.title, self.type)

    @models.permalink
    def get_absolute_url(self):
        return ('cm-group-detail', None, {'slug': self.slug})

    def save(self, *args, **kwargs):
        if self.disbanded_on and self.active:
            self.active = False
        super(Group, self).save(*args, **kwargs)

    @property
    def current_terms(self):
        return Term.active_objects.filter(group=self)

    @property
    def past_terms(self):
        objects=[]
        for t in Term.objects.all().filter(group=self):
            if not t in Term.active_objects.all().filter(group=self):
                objects.append(t)
        return objects

class Office(TimeStampedModel, TitleSlugDescriptionModel):
    '''
    Office model.

    Holds all the various office types, mostly just drawn from django-extension mixins. Designed to take care of pres, vp, sec, tres type positions.

    '''
    group=models.ForeignKey(Group)
    order=models.IntegerField(_('Office order'), max_length=2)
    
    class Meta:
        verbose_name = _('Office')
        verbose_name_plural = _('Offices')
        ordering = ('order', 'group',)

    def __unicode__(self):
        return u'%s of %s' % (self.title, self.group)


class Term(TimeStampedModel):
    group = models.ForeignKey(Group)
    start = models.DateField(_('Start'))
    end = models.DateField(_('End'), blank=True, null=True)
    office = models.ForeignKey(Office, blank=True, null=True)
    alternate = models.BooleanField(_('Alternate'), default=False)
    person=models.ForeignKey('Person', blank=True, null=True)
    
    objects = models.Manager()
    board_members = BoardManager()
    active_objects = ActiveTermManager()

    class Meta:
        verbose_name = _('Term')
        verbose_name_plural = _('Terms')
        ordering = ('-office','start',)
        get_latest_by = 'start'
   
    @property
    def active(self):
        status=False
        if self.start <= datetime.now().date():
            if self.end:
                if self.end >= datetime.now().date():
                    status = True
            else:
                status=True
        return status
    
    @property
    def length(self):
        if self.end: return (self.end.year - self.start.year)
        else: return None
    
    @property
    def officer(self):
        if self.office: return True
        else: return False

    def __unicode__(self):
        if self.officer: desc=self.office
        else: desc=u'%s member' % (self.group)
        
        if self.alternate: str=u'%s - alternate (%s)' % (self.person, self.start.year)
        else: str=u'%s - %s (%s)' %(self.person, desc, self.start.year)
        return str

    @models.permalink
    def get_absolute_url(self):
        if self.office: return ('cm-term-detail', None, {'slug': self.group.slug, 'office_slug': self.office.slug, })
        else: return None

class Person(models.Model):
    """Person model."""
    GENDER_CHOICES = (
        (1, 'Male'),
        (2, 'Female'),
    )
    first_name = models.CharField(_('first name'), blank=True, max_length=100)
    middle_name = models.CharField(_('middle name'), blank=True, max_length=100)
    last_name = models.CharField(_('last name'), blank=True, max_length=100)
    slug = models.SlugField(_('slug'), unique=True)
    user = models.ForeignKey(User, blank=True, null=True, help_text='If the person is an existing user of your site.')
    gender = models.PositiveSmallIntegerField(_('gender'), choices=GENDER_CHOICES, blank=True, null=True)
    member = models.BooleanField(_('Member'), default=True, help_text='Is this person a member of the organization?')
    phone = PhoneNumberField(_('Phone'), blank=True, null=True)
    email = models.EmailField(_('Email'), blank=True, null=True)

    class Meta:
        verbose_name = _('person')
        verbose_name_plural = _('people')
        ordering = ('last_name', 'first_name',)

    def __unicode__(self):
        return u'%s' % self.full_name

    @property
    def full_name(self):
        return u'%s %s' % (self.first_name, self.last_name)

    @models.permalink
    def get_absolute_url(self):
        return ('cm-person-detail', None, {'slug': self.slug})

class Meeting(MarkupMixin, TimeStampedModel, Event):
    '''
    Meeting model.

    A general meeting model. 
    '''
    group = models.ForeignKey(Group)
    location = models.CharField(_('Location'), blank=True, null=True, max_length=150)
    agenda = models.TextField(_('Agenda'), blank=True, null=True)
    rendered_agenda = models.TextField(_('Rendered agenda'), blank=True, null=True)
    business_arising=models.TextField(_('Business arising'), blank=True, null=True)

    def __init__(self, *args, **kwargs):
        super (Meeting, self).__init__(*args, **kwargs)
        self._next = None
        self._previous = None

    class Meta:
        verbose_name = _('Meeting')
        verbose_name_plural = _('Meetings')
        ordering = ('start',)

    class MarkupOptions:
        source_field = 'agenda'
        rendered_field = 'rendered_agenda'

    def __unicode__(self):
        return u'%s meeting - %s' % (self.group, self.start)

    @models.permalink
    def get_absolute_url(self):
        return ('cm-meeting-detail', (), {'slug': self.group.slug, 'year': self.start.year, 'month': self.start.month, })

    @property
    def start_date(self):
        return self.start.date

    @property
    def start_time(self):
        return self.start.time

    @property
    def end_date(self):
        return self.end.date

    @property
    def end_time(self):
        return self.end.time

    def get_next_meeting(self):
        """Determines the next meeting"""

        if not self._next:
            try:
                qs = Meeting.objects.filter(calendar=self.calendar).exclude(id__exact=self.id)
                meeting= qs.filter(start__gte=self.start).order_by('start')[0]
            except (Meeting.DoesNotExist, IndexError):
                meeting = None
            self._next = meeting 

        return self._next

    def get_previous_meeting(self):
        """Determines the previous meeting"""

        if not self._previous:
            try:
                qs = Meeting.objects.all().exclude(id__exact=self.id)
                meeting= qs.filter(start__lte=self.start).order_by('-start')[0]
            except (Meeting.DoesNotExist, IndexError):
                meeting = None
            self._previous = meeting 

        return self._previous

class Minutes(MarkupMixin, TimeStampedModel):
    meeting = models.ForeignKey(Meeting)
    call_to_order = models.TimeField(_('Call to order'), blank=True, null=True)
    members_present = models.ManyToManyField(Term)
    others_present= models.ManyToManyField(Person)
    content = models.TextField(_('Content'))
    rendered_content = models.TextField(_('Rendered content'), blank=True, null=True, editable=False)
    adjournment = models.TimeField(_('Adjournment'), blank=True, null=True)
    signed = models.ForeignKey(Person, related_name="signed_by")
    signed_date = models.DateField(_('Signed date'), default=datetime.now())
    draft = models.BooleanField(_('Draft'), default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = _('Minutes')
        verbose_name_plural = _('Minutes')
        ordering = ('meeting',)

    class MarkupOptions:
        source_field = 'content'
        rendered_field = 'rendered_content'

    def __unicode__(self):
        return u'Minutes from %s' % (self.meeting)

    @models.permalink
    def get_absolute_url(self):
        return ('cm-minutes-detail', (), {'slug':self.meeting.meeting.group.slug, 'year': self.meeting.meeting.start.year, 'month': self.meeting.meeting.event.start.month, })


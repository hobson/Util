#!/usr/bin/env python
#
#    Filename: 
#
#    Author:	Thomas L. Marshall <tlm@altmx.com>
#    Date:	Sat May 10 12:04:14 PDT 2014
#
#    Description:
#        This program is intended to fetch my LinkedIn profile data
#        and convert it to a resume. While I would like to believe
#        that this is an expression of laziness and intent to do
#        other things that I enjoy, the sad and boring truth is that
#        I like writing code and find this task as simply much more
#        fun than transcribing and/or maintaining multiple resumes
#
#    History:
#        2014-05-10.01 - created.
#
#  ====================================================================

import oauth2
import cjson
import re
import textwrap

from os.path import expanduser
from enchant.checker import SpellChecker

from odf.opendocument import OpenDocumentText
from odf.style import Style, TextProperties, ParagraphProperties, TableColumnProperties
from odf.table import Table, TableColumn, TableRow, TableCell
from odf.text import A, P, Span

def max(a,b) :
    if a > b :
        return a
    return b

def min(a,b) :
    if a < b :
        return a
    return b

class Error(Exception) :
    pass

# simple config file to ignore blank lines and lines beginning with
# a # character. everything else is split into key/value pairs and
# stuffed into a dictionary
class Config :
    def __init__(self, filename) :
        self.filename = filename
        self.data = {}
        self.data['page_width'] = 72
        self.data['skills_cols'] = 5
        self.data['skills_max'] = 1000
        self.data['experience_max'] = 1000
        self.data['certificates_max'] = 1000
        self.data['fields'] = 'first-name,last-name,industry,main-address,' +\
            'email-address,member-url-resources,phone-numbers,' +\
            'headline,location,num-recommenders,current-status,' +\
            'summary,skills,positions,educations,certifications:' +\
            '(name,authority,start-date),interests,languages:' +\
            '(language,proficiency)'
        self.load()

    # read/load the config file
    def load(self) :
        try :
            f = open(self.filename, 'r')
            for line in f :
                line = line.strip()
                if not line or re.match('#', line) :
                    continue
                [k, v] = re.split('\s+', line, 1)
                self.data[k] = v
            f.close
        except IOError :
            pass
    
    # fetch value by key and return it (if it exists)
    def fetch(self, key) :
        if self.data[key] :
            return self.data[key]
        return None
    
class App :
    def __init__(self) :
        self.home = expanduser('~')
        self.config = Config(self.home + '/.jitconfig')

# class to manage the interface to LinkedIn
class LinkedIn(App) :
    def __init__(self) :
        App.__init__(self)

    # linkedin requires a set of tokens to fetch data. a pair of 
    # application keys and a pair of user keys. I think that these
    # are independent meaning that the app tokens stay with the app
    # and the user tokens  are associated with the target resume
    # data. I have only used this with my resume so I'm not sure how
    # go about getting just the uset token pair.
    def getProfile(self) :
        ouser = oauth2.Consumer(self.config.fetch('api_key'),
                                self.config.fetch('secret_key'))
        token = oauth2.Token(key=self.config.fetch('user_token'),
                             secret=self.config.fetch('user_secret'))
        client = oauth2.Client(ouser, token)
        req = 'http://api.linkedin.com/v1/people/~:(' +\
              self.config.fetch('fields') + \
              ')?format=json&secure-urls=true'
        response, result = client.request(req, 'GET', '')
        return result

class Resume(App) :
    def __init__(self) :
        App.__init__(self)
        self.width = int(self.config.fetch('page_width'))
        # regarding adding words to the spell checker, I didn't
        # want to deal with the overhead of an user interface here
        # so I simply added a list of words to .config/enchant/en_US.dic
        # (local dictionary) I think that is what some other UI would
        # do anyway and now these words are available to other apps.
        self.chkr = SpellChecker("en_US")
        # keep a local copy cached to minimize the number of
        # requests to linkedin and to provide "offline" access
        # to the most recently downloaded version.
        # remember to delete this file after you edit your
        # linkedin profile
        try :
            f = open(self.home + '/.jitresume', 'r');
            profile = f.read();
        except IOError :
            conn = LinkedIn()
            profile = conn.getProfile()
            f = open(self.home + '/.jitresume', 'w');
            f.write(profile)
        finally :
            self.data = cjson.decode(profile)
            f.close()
    
    # essentially, all the "content" methods are convenience wrappers
    # that return 1 or more (tuples) strings of content from the data
    # container. This allows formatting wrappers (Text, HTML, etc) to
    # focus on the task of presentation separate from the data tasks.
    def pre(self) :
        return ''

    def post(self) :
        return ''

    # returns resume header content
    def header(self) :
        return (self.data['firstName'] + ' ' + self.data['lastName'],
                self.data['mainAddress'], self.data['emailAddress'],
                self.data['memberUrlResources']['values'][0]['url'],
                self.data['phoneNumbers']['values'][0]['phoneNumber'])

    # returns the text of a the professional summary
    def summary(self) :
        tmp = self.data['summary']
        self.chkr.set_text(tmp)
        for err in self.chkr :
            print "spell warning:", err.word
        return '\n'.join(textwrap.wrap(tmp, self.width))

    # generates a limited number of skills taken from the linkedin data
    def skills(self) :
        num = min(len(self.data['skills']['values']),
                  int(self.config.fetch('skills_max')))
        count = 0
        while count < num :
            yield self.data['skills']['values'][count]['skill']['name']
            count += 1

    # generates tuples of content for each position in the linkedin
    # data set. company name, date range, title, and summary.
    def experience(self) :
        num = min(len(self.data['positions']['values']),
                  int(self.config.fetch('experience_max')))
        count = 0
        while count < num :
            tmp = self.data['positions']['values'][count]
            summary = tmp['summary']
            self.chkr.set_text(summary)
            for err in self.chkr :
                print "spell warning:", err.word
            summary = '\n'.join(textwrap.wrap(summary, self.width))
            endDate = 'Present'
            if tmp.has_key('endDate') :
                endDate = str(tmp['endDate']['year'])
            dates = str(tmp['startDate']['year']) + ' - ' + endDate
            yield (tmp['company']['name'].upper(),
                   dates, tmp['title'], summary)
            count += 1

    # generates tuples of content for each school in the linkedin
    # data set. school name, graduation date, and degree.
    def education(self) :
        num = len(self.data['educations']['values'])
        count = 0
        while count < num :
            tmp = self.data['educations']['values'][count]
            # only want one date, preferrably the end date
            year = ''
            if tmp.has_key('startDate') :
                year = str(tmp['startDate']['year'])
            if tmp.has_key('endDate') :
                year = str(tmp['endDate']['year'])
            # degree is a combination of field of study and
            # degree if attained (some combination ofeither)
            field = ''
            if tmp.has_key('fieldOfStudy') :
                field = str(tmp['fieldOfStudy'])
            degree = ''
            if tmp.has_key('degree') :
                degree = tmp['degree'] + ', '
                # here I prefer the language "Bachelor of Science" to
                # "Bachelor's degree". That being said, linkedin does
                # provide a suitable domain to map to a complete
                # range of options. Add or modify here as needed.
                if re.match('^Bachelor', tmp['degree']) :
                    degree = 'Bachelor of Science, '
            degree += field
            yield (tmp['schoolName'].upper(), year, degree)
            count += 1

    # generates tuples of content for each certification in the
    # linkedin data set. certification, date granted, authority
    def certifications(self) :
        num = min(len(self.data['certifications']['values']),
                  int(self.config.fetch('certificates_max')))
        count = 0
        while count < num :
            tmp = self.data['certifications']['values'][count]
            authority = ''
            if tmp.has_key('authority') :
                authority = tmp['authority']['name'] + '\n'
            # just one date, preferrably the date granted
            year = ''
            if tmp.has_key('startDate') :
                year = str(tmp['startDate']['year'])
            if tmp.has_key('endDate') :
                year = str(tmp['endDate']['year'])
            yield (tmp['name'].upper(), year, authority)
            count += 1

    # generates a tuple pair of language and proficiency
    # for each language in the linkedin data set.
    def languages(self) :
        num = len(self.data['languages']['values'])
        count = 0
        while count < num :
            tmp = self.data['languages']['values'][count]
            # I think that the proficiency is optional or
            # returns a defauly vaule... Just in case:
            proficiency = tmp['proficiency']['name']
            if tmp.has_key('proficiency') :
                profeciency = tmp['proficiency']['name']
            yield (tmp['language']['name'], proficiency)
            count += 1

    def interests(self) :
        interests = self.data['interests']
        self.chkr.set_text(interests)
        for err in self.chkr :
            print "spell warning:", err.word
        return '\n'.join(textwrap.wrap(interests, self.width))

    def content(self) :
        return self.data

# TextResume formats the resume in a Text format with some word
# wrapping and someminimal layout
class TextResume(Resume) :
    def __init__(self) :
        Resume.__init__(self)

    def header(self) :
        width = str(self.width)
        v,w,x,y,z = Resume.header(self)
        # LinkedIn sends a newline between the street and city/state/zip
        # this tends to mess up the formatting. THis could be together
        # (as is) or changed to be on separate lines.
        street,csz = re.split('\n', w)
        return ('{:^{}}\n{:^{}}\n{:^{}}\n{:^{}}\n{:^{}}\n'
               ).format(v,width,street + ' ' + csz,
                        width,y,width,x,width,z,width)

    def summary(self) :
        return 'PROFESSIONAL SUMMARY\n{}\n'.format(Resume.summary(self))
    
    def skills(self) :
        result = 'RELEVANT SKILLS\n'
        skills_cols = int(self.config.fetch('skills_cols'))
        col = 0
        tmp = '{:<'+str(self.width/skills_cols)+'}'
        for skill in Resume.skills(self) :
            col += 1
            result += tmp.format(skill)
            if col == skills_cols :
                col = 0
                result += '\n'
        if col > 0 :
            result += '\n'
        return result

    def experience(self) :
        s = 'EXPERIENCE'
        tmp = '\n{:<' + str(self.width - 14) + '}{:>14}\n{}\n{}\n'
        for v,w,x,y in Resume.experience(self) :
            s += tmp.format(v, w, x, y)
        return s
    
    def education(self) :
        s = 'EDUCATION'
        tmp = '\n{:<' + str(self.width - 4) + '}{:>4}\n{}\n'
        for v,w,x in Resume.education(self) :
            s += tmp.format(v,w,x)
        return s

    def certifications(self) :
        s = 'CERTIFICATIONS'
        tmp = '\n{:<' + str(self.width - 4) + '}{:>4}\n{}'
        for v,w,x in Resume.certifications(self) :
            s += tmp.format(v,w,x)
        return s
        
    def languages(self) :
        s = 'LANGUAGES'
        tmp = '\n{} ({})\n'
        for v,w in Resume.languages(self) :
            s += tmp.format(v, w)
        return s
        
    def interests(self) :
        return 'INTERESTS\n{}'.format(Resume.interests(self))
        
    def content(self) :
        return '\n'.join([self.header(), self.summary(), self.skills(),
                          self.experience(), self.education(),
                          self.certifications(), self.languages(),
                          self.interests()])

class HTMLResume(Resume) :
    def __init__(self) :
        Resume.__init__(self)
        self.sectmpl = '\t<div class="section">\n\t    ' +\
                       '<span class="shdr">{}</span><hr/>\n{}\n\t</div>'

    def pre(self) :
        s = '''<!DOCTYPE html>
<html>
    <head>
        <style>
             body            {{ font-family: serif; font-size: 10pt;
                                margin: 18pt 36px; }}
             p               {{ text-align: justify; }}
             p.lang          {{ margin: 0px 0px 5px 0px;}}
             p.interests     {{ text-align: justify; }}
             a               {{ text-decoration: none; }}
             a:hover         {{ text-decoration: underline; }}
             div.header      {{ text-align: center; }}
             div.section     {{ margin-top: 15px; }}
             span.name       {{ font-weight: bold; }}
             span.shdr       {{ font-weight: bold; }}
             span.lang       {{ font-weight: bold; }}
             table           {{ border: none; }}
             table.experience {{ margin-bottom: 5px; }}
             table.education {{ margin-bottom: 5px; }}
             table.certification {{ margin-bottom: 5px; }}
             td.company      {{ font-weight: bold; }}
             td.institution  {{ font-weight: bold; }}
             td.title        {{ font-weight: bold; font-style: italic; }}
             td.dates        {{ text-align: right; font-style: italic; }}
             td.degree       {{ font-weight: bold; font-style: italic; }}
             td.authority    {{ font-weight: bold; font-style: italic; }}
             td.summary      {{ text-align: justify; }}
        </style>
    </head>
    <body>'''
        return s.format()

    def post(self) :
        s = '''
    </body>
</html>'''
        return s.format()

    def header(self) :
        v,w,x,y,z = Resume.header(self)
        s = '''
        <div class="header">
            <span class="name">{0}</span></br>
            {1}<br/>
            <a href="mailto:{2}?subject=job%20opportunity">{2}</a><br/>
            <a href="{3}">{3}</a><br/>
            {4}
        </div>'''
        return s.format(v,w,x,y,z)

    def summary(self) :
        s = self.sectmpl.format('PROFESSIONAL SUMMARY', '{}')
        return s.format('<p>{}</p>'.format(Resume.summary(self)))

    def skills(self) :
        s = self.sectmpl.format('RELEVANT SKILLS',
                                '<table class="skills" width="100%">' +\
                                '    {}\n</table>')
        col = 0
        tmp = ''
        row = ''
        skills_cols = int(self.config.fetch('skills_cols'))
        for v in Resume.skills(self) :
            col += 1
            if col % skills_cols > 0 :
                row += ('<td class="skill" width="{:.1%}">{}' +\
                        '</td>').format(1.0/skills_cols,v)
            # rounding up may leave this over 100% so just leave
            # the last cell without a width to pick up any slack
            else :
                row += '<td>{}</td>'.format(v)
                tmp += '\n     <tr>{}</tr>'.format(row)
                row = ''
        if col % skills_cols > 0:
            tmp += '\n     <tr>{}</tr>'.format(row)
        return s.format(tmp)

    def experience(self) :
        s = self.sectmpl.format('EXPERIENCE', '{}')
        tmp = ''
        for v,w,x,y in Resume.experience(self) :
            tmp += '''
    <table class="experience" width="100%">
        <tr><td class="company">{}</td>
            <td class="dates">{}</td></tr>
        <tr><td class="title" colspan="2">{}</td></tr>
        <tr><td class="summary" colspan="2">{}</td></tr>
    </table>'''.format(v, w, x, y)
        return s.format(tmp)

    def education(self) :
        s = self.sectmpl.format('EDUCATION', '{}')
        tmp = ''
        for v,w,x in Resume.education(self) :
            tmp += '''
    <table class="education" width="100%">
        <tr><td class="institution">{}</td>
            <td class="dates">{}</td></tr>
        <tr><td class="degree" colspan="2">{}</td></tr>
    </table>'''.format(v,w,x)
        return s.format(tmp)

    def certifications(self) :
        s = self.sectmpl.format('CERTIFICATIONS', '{}')
        tmp = ''
        for v,w,x in Resume.certifications(self) :
            tmp += '''
    <table class="certification" width="100%">
        <tr><td class="institution">{}</td>
            <td class="dates">{}</td></tr>
        <tr><td class="authority" colspan="2">{}</td></tr>
    </table>'''.format(v,w,x)
        return s.format(tmp)

    def languages(self) :
        s = self.sectmpl.format('LANGUAGES', '{}')
        languages = ''
        tmp = '<p class="lang"><span class="lang">{}</span> ({})</p>\n'
        for v,w in Resume.languages(self) :
            languages += tmp.format(v, w)
        return s.format(languages)

    def interests(self) :
        s = self.sectmpl.format('INTERESTS', '{}')
        return s.format(''.join(['<p class="interests">',
                                 Resume.interests(self), '<p>']))

    def content(self) :
        return ''.join([self.pre(), self.header(), self.summary(),
                        self.skills(), self.experience(), self.education(),
                        self.certifications(), self.languages(),
                        self.interests(), self.post()])

# OpenDocument Formatter for the Resume content
class ODFResume(Resume) :
    def __init__(self, filename) :
        Resume.__init__(self)
        self.filename = filename
        self.doc = OpenDocumentText()
    
    # create a bunch of styles for the different sections. These should
    # be able to be paired down to something more reasonable. At this
    # point, however, it seems to be a bit of trial and error since
    # the odfpy documentation is still in process
    def pre(self) :
        # parent of all styles
        s = self.doc.styles
        style = Style(name="Standard", family="paragraph")
        s.addElement(style)
        # my name style (header info)
        style = Style(name="MyName", family="paragraph",
                      parentstylename='Standard', displayname="MyName")
        style.addElement(ParagraphProperties(textalign="center"))
        style.addElement(TextProperties(fontsize="13pt",fontweight="bold"))
        s.addElement(style)
        # my body style (header info)
        style = Style(name="MyBody", family="paragraph",
                      parentstylename='Standard', displayname="MyBody")
        style.addElement(ParagraphProperties(textalign="center"))
        style.addElement(TextProperties(fontsize="11pt"))
        s.addElement(style)
        # my links (header info)
        style = Style(name="MyLink", family="paragraph",
                      parentstylename='Standard', displayname="MyLink")
        style.addElement(ParagraphProperties(textalign="center"))
        style.addElement(TextProperties(color="#0000FF"))
        style.addElement(TextProperties(fontsize="11pt",fontstyle="italic"))
        s.addElement(style)
        # section heading style
        # this style has a top margin to provide a bit of breathing room
        # from the previous content
        style = Style(name="Heading", family="paragraph",
                      parentstylename='Standard', displayname="Heading")
        style.addElement(ParagraphProperties(margintop="0.15in"))
        style.addElement(TextProperties(fontsize="12pt",fontweight="bold"))
        s.addElement(style)
        # name style
        # small top margin to provide some space between items in the list
        # of jobs, schools and certifications
        style = Style(name="Name", family="paragraph",
                      parentstylename='Standard', displayname="Name")
        style.addElement(ParagraphProperties(margintop="0.1in"))
        style.addElement(TextProperties(fontsize="11pt",fontweight="bold"))
        s.addElement(style)
        # Right Aligned Italic
        # this right alignment is paired with the Name style since it will be
        # used for dates to the right of names. For proper alignment, it also
        # needs a small top margin
        style = Style(name="RightItalic", family="paragraph",
                      parentstylename='Standard', displayname="RightItalic")
        style.addElement(ParagraphProperties(margintop="0.1in",
                                             textalign="right"))
        style.addElement(TextProperties(fontsize="11pt",fontstyle="italic"))
        s.addElement(style)
        # position title style
        style = Style(name="Title", family="paragraph",
                      parentstylename='Standard', displayname="Title")
        style.addElement(TextProperties(fontsize="11pt",fontstyle="italic",
                                        fontweight="bold"))
        s.addElement(style)
        # body style
        style = Style(name="Body", family="paragraph",
                      parentstylename='Standard', displayname="Body")
        style.addElement(ParagraphProperties(textalign="justify"))
        style.addElement(TextProperties(fontsize="11pt"))
        s.addElement(style)
        # list style
        style = Style(name="List", family="paragraph",
                      parentstylename='Standard', displayname="List")
        style.addElement(ParagraphProperties(margintop="0.05in"))
        style.addElement(ParagraphProperties(textalign="left"))
        style.addElement(TextProperties(fontsize="11pt"))
        s.addElement(style)
        # Italic
        style = Style(name="Italic", family="paragraph",
                      parentstylename='Standard', displayname="Italic")
        style.addElement(TextProperties(fontsize="11pt",fontstyle="italic"))
        s.addElement(style)
        # Automatic Styles
        # Bold
        style = Style(name="Bold", displayname="Bold", family="text")
        style.addElement(TextProperties(fontweight="bold"))
        self.doc.automaticstyles.addElement(style)
        # wide column
        style = Style(name="widecolumn", displayname="widecolumn",
                      family="table-column")
        style.addElement(TableColumnProperties(columnwidth="6.0in"))
        self.doc.automaticstyles.addElement(style)
        # wide column
        style = Style(name="narrowcolumn", displayname="narrowcolumn",
                      family="table-column")
        style.addElement(TableColumnProperties(columnwidth="1.0in"))
        self.doc.automaticstyles.addElement(style)
               
    def post(self) :
        pass

    # creates a side by side (two column) layout for the name and date
    # pairs used in experience, education and certifications
    def NameDatePair(self, a, b) :
        table = Table(name="t")
        table.addElement(TableColumn(numbercolumnsrepeated="1",
                                     stylename="widecolumn"))
        table.addElement(TableColumn(numbercolumnsrepeated="1",
                                     stylename="narrowcolumn"))
        tr = TableRow()
        tc = TableCell(valuetype="string")
        tc.addElement(P(text=a,stylename="Name"))
        tr.addElement(tc)             
        tc = TableCell(valuetype="string")
        tc.addElement(P(text=b,stylename="RightItalic"))
        tr.addElement(tc)             
        table.addElement(tr)
        return table

    # lays out the first page header with name and contact info
    def header(self) :
        t = self.doc.text
        name,x,email,url,phone = Resume.header(self)
        t.addElement(P(text=name, stylename="MyName"))
        street,csz = re.split('\n', x)
        t.addElement(P(text=street + ' ' + csz, stylename="MyBody"))
        p = P(stylename="MyLink")
        emailURL= 'mailto:' + email + '?subject=your%20resume'
        p.addElement(A(type="simple", href=emailURL, text=email))
        t.addElement(p)
        p = P(stylename="MyLink")
        p.addElement(A(type="simple", href=url, text=url))
        t.addElement(p)
        t.addElement(P(text=phone, stylename="MyBody"))

    # the summary is a simple heading + the summary paragraph
    def summary(self) :
        t = self.doc.text
        t.addElement(P(text='PROFESSIONAL SUMMARY', stylename="Heading"))
        t.addElement(P(text=Resume.summary(self), stylename="Body"))

    def skills(self) :
        t = self.doc.text
        t.addElement(P(text='RELEVANT SKILLS', stylename="Heading"))
        table = Table(name="skills-table")
        col = 0
        skills_cols = int(self.config.fetch('skills_cols'))
        table.addElement(TableColumn(numbercolumnsrepeated=skills_cols))
        for skill in Resume.skills(self) :
            if col % skills_cols == 0 :
                tr = TableRow()
                table.addElement(tr)
            tc = TableCell(valuetype="string")
            tc.addElement(P(text=skill,stylename="List"))
            tr.addElement(tc)             
            col += 1
        t.addElement(table)

    def experience(self) :
        t = self.doc.text
        t.addElement(P(text='EXPERIENCE', stylename="Heading"))
        for company,dates,position,summary in Resume.experience(self) :
            t.addElement(self.NameDatePair(company, dates))
            t.addElement(P(text=position, stylename="Title"))
            t.addElement(P(text=summary, stylename="Body"))

    def education(self) :
        t = self.doc.text
        t.addElement(P(text='EDUCATION', stylename="Heading"))
        for school,date,degree in Resume.education(self) :
            t.addElement(self.NameDatePair(school, date))
            t.addElement(P(text=degree, stylename="Title"))

    def certifications(self) :
        t = self.doc.text
        t.addElement(P(text='CERTIFICATIONS', stylename="Heading"))
        for name,date,authority in Resume.certifications(self) :
            t.addElement(self.NameDatePair(name, date))
            t.addElement(P(text=authority, stylename="Title"))

    def languages(self) :
        t = self.doc.text
        t.addElement(P(text='LANGUAGES', stylename="Heading"))
        for language,proficiency in Resume.languages(self) :
            p = P(stylename="List")
            p.addElement(Span(text=language, stylename="Bold"))
            p.addElement(Span(text=' (' + proficiency + ')'))
            t.addElement(p)

    def interests(self) :
        t = self.doc.text
        t.addElement(P(text='INTERESTS', stylename="Heading"))
        t.addElement(P(text=Resume.interests(self), stylename="Body"))

    def content(self) :
        self.pre()
        self.header()
        self.summary()
        self.skills()
        self.experience()
        self.education()
        self.certifications()
        self.languages()
        self.interests()
        self.post()
        self.doc.save(self.filename)

def main() :
    ODFResume('myresume.odt').content()
#     print HTMLResume().content()
#     print TextResume().content()
    

if __name__ == '__main__' :
    main()

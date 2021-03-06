# -*- coding: iso-8859-1 -*-
# Copyright (C) 2014 Daniele Simonetti
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import sys
import os
import shutil
import models
import exporters
import dal
import dal.query
import dal.dataimport
import osutil
from math import ceil
from tempfile import mkstemp
import subprocess

from PySide import QtCore, QtGui

APP_NAME    = 'l5rcm'
APP_DESC    = 'Legend of the Five Rings: Character Manager'
APP_VERSION = '3.9.5'
DB_VERSION  = '3.0'
APP_ORG     = 'openningia'

PROJECT_PAGE_LINK      = 'http://code.google.com/p/l5rcm/'
BUGTRAQ_LINK           = 'http://code.google.com/p/l5rcm/issues/list'
PROJECT_PAGE_NAME      = 'Project Page'
AUTHOR_NAME            = 'Daniele Simonetti'
L5R_RPG_HOME_PAGE      = 'http://www.l5r.com/rpg/'
ALDERAC_HOME_PAGE      = 'http://www.alderac.com/'
PROJECT_DOWNLOADS_LINK = 'https://sourceforge.net/projects/l5rcm/'

L5RCM_GPLUS_PAGE  = "https://plus.google.com/114911686277310621574"
L5RCM_GPLUS_COMM  = "https://plus.google.com/communities/107752342280671357654"

MY_CWD        = os.getcwd()
if not os.path.exists( os.path.join( MY_CWD, 'share/l5rcm') ):
    MY_CWD = sys.path[0]
    if not os.path.exists( os.path.join( MY_CWD, 'share/l5rcm') ):
        MY_CWD = os.path.dirname(sys.path[0])

def get_app_file(rel_path):
    if os.name == 'nt':
        return os.path.join( MY_CWD, 'share/l5rcm', rel_path )
    else:
        sys_path = '/usr/share/l5rcm'
        if os.path.exists( sys_path ):
            return os.path.join( sys_path, rel_path )
        return os.path.join( MY_CWD, 'share/l5rcm', rel_path )

def get_app_icon_path(size = (48,48)):
    size_str = '%dx%d' % size
    if os.name == 'nt':
        return os.path.join( MY_CWD, 'share/icons/l5rcm/%s' % size_str, APP_NAME + '.png' )
    else:
        sys_path = '/usr/share/icons/l5rcm/%s' % size_str
        if os.path.exists( sys_path ):
            return os.path.join( sys_path, APP_NAME + '.png' )
        return os.path.join( MY_CWD, 'share/icons/l5rcm/%s' % size_str, APP_NAME + '.png' )

def get_tab_icon(name):
    if os.name == 'nt':
        return os.path.join( MY_CWD, 'share/icons/l5rcm/tabs/', name + '.png' )
    else:
        sys_path = '/usr/share/icons/l5rcm/tabs/'
        if os.path.exists( sys_path ):
            return os.path.join( sys_path, name + '.png' )
        return os.path.join( MY_CWD, 'share/icons/l5rcm/tabs/', name + '.png' )

def get_icon_path(name, size = (48,48)):
    base = "share/icons/l5rcm/"
    if size is not None:
        base += '%dx%d' % size

    if os.name == 'nt':
        return os.path.join( MY_CWD, base, name + '.png' )
    else:
        sys_path = '/usr/' + base
        if os.path.exists( sys_path ):
            return os.path.join( sys_path, name + '.png' )
        return os.path.join( MY_CWD, base, name + '.png' )

class CMErrors(object):
    NO_ERROR      = 'no_error'
    NOT_ENOUGH_XP = 'not_enough_xp'

class L5RCMCore(QtGui.QMainWindow):

    dstore = None

    def __init__(self, locale, parent = None):
        super(L5RCMCore, self).__init__(parent)
        #print(repr(self))
        self.pc = None

        # character stored insight rank
        # used to knew if the character
        # get new insight rank
        self.last_rank = 1

        # Flag to lock advancement refunds in order
        self.lock_advancements = True

        # current locale
        self.locale = locale

        # load data
        self.reload_data()

    def reload_data(self):
        settings = QtCore.QSettings()
        self.data_pack_blacklist = settings.value('data_pack_blacklist', [])

        # Data storage
        if not self.dstore:
            self.dstore = dal.Data(
                [osutil.get_user_data_path('core.data'),
                 osutil.get_user_data_path('data'),
                 osutil.get_user_data_path('data.' + self.locale)],
                 self.data_pack_blacklist)
        else:
            print('Re-loading datapack data')
            self.dstore.rebuild(
                    [osutil.get_user_data_path('core.data'),
                    osutil.get_user_data_path('data'),
                    osutil.get_user_data_path('data.' + self.locale)],
                    self.data_pack_blacklist)

    def check_datapacks(self):
        if len(self.dstore.get_packs()) == 0:
            self.advise_warning(self.tr("No Datapacks installed"),
                                self.tr("Without data packs the software will be of little use."
                                        "<p>Download a datapack from <a href=\"{0}\">{0}</a>.</p>"
                                        .format(PROJECT_DOWNLOADS_LINK)))

    def update_from_model(self):
        pass

    def export_as_text(self, export_file):
        exporter = exporters.TextExporter()
        exporter.set_form (self)
        exporter.set_model(self.pc     )

        f = open(export_file, 'wt')
        if f is not None:
            exporter.export(f)
        f.close()

    def create_fdf(self, exporter):

        exporter.set_form (self)
        exporter.set_model(self.pc)

        fd, fpath = mkstemp(suffix='.fdf', text=False)
        with os.fdopen(fd, 'wb') as fobj:
            exporter.export(fobj)
        return fpath

    def flatten_pdf(self, fdf_file, source_pdf, target_pdf, target_suffix = None):
        basen = os.path.splitext(os.path.basename(target_pdf))[0]
        based = os.path.dirname (target_pdf)

        if target_suffix:
            target_pdf = os.path.join(based, basen) + '_%s.pdf' % target_suffix
        else:
            target_pdf = os.path.join(based, basen) + '.pdf'

        # call pdftk
        args_ = [self.get_pdftk(), source_pdf, 'fill_form', fdf_file, 'output', target_pdf, 'flatten']
        subprocess.call(args_)
        self.try_remove(fdf_file)
        print('created pdf {0}'.format(target_pdf))

    def merge_pdf(self, input_files, output_file):
        # call pdftk
        args_ = [self.get_pdftk()] + input_files + ['output', output_file]
        subprocess.call(args_)
        for f in input_files:
            self.try_remove(f)

    def get_pdftk(self):
        if sys.platform == 'win32':
            return os.path.join(MY_CWD, 'tools', 'pdftk.exe')
        elif sys.platform == 'linux2':
    		sys_path = '/usr/bin/pdftk'
    		loc_path = os.path.join(MY_CWD, 'tools', 'pdftk')
    		if os.path.exists(sys_path): return sys_path
    		else: return loc_path
        elif sys.platform == 'darwin':
            return os.path.join(MY_CWD, 'tools', 'pdftk')
        return None

    def try_remove(self, fpath):
        try:
            os.remove(fpath)
            print('deleted temp file: {0}'.format(fpath))
        except:
            print('cannot delete temp file: {0}'.format(fpath))

    def write_pdf(self, source, exporter):
        source_pdf = get_app_file(source)
        source_fdf = self.create_fdf(exporter)
        fd, fpath = mkstemp(suffix='.pdf');
        os.fdopen(fd, 'wb').close()
        self.flatten_pdf(source_fdf, source_pdf, fpath)
        self.temp_files.append( fpath )

    def commit_pdf_export(self, export_file):
        if os.path.exists(export_file):
            os.remove(export_file)

        if len(self.temp_files) > 1:
            self.merge_pdf(self.temp_files, export_file)
        elif len(self.temp_files) == 1:
            shutil.move(self.temp_files[0], export_file)

    def export_npc_characters(self, npc_files, export_file):
        self.temp_files = []

        pcs = []
        for f in npc_files:
            c = models.AdvancedPcModel()
            if c.load_from(f):
                pcs.append(c)

        self.write_pdf( 'sheet_npc.pdf', exporters.FDFExporterTwoNPC( self.dstore, pcs ) )
        self.commit_pdf_export( export_file )

    def export_as_pdf(self, export_file):
        self.temp_files = []

        # GENERIC SHEET
        source_pdf = get_app_file('sheet_all.pdf')
        source_fdf = self.create_fdf(exporters.FDFExporterAll())
        fd, fpath = mkstemp(suffix='.pdf');
        os.fdopen(fd, 'wb').close()

        self.flatten_pdf(source_fdf, source_pdf, fpath)
        self.temp_files.append(fpath)

        # SAMURAI MONKS ALSO FITS IN THE BUSHI CHARACTER SHEET
        is_monk, is_brotherhood = self.pc_is_monk    ()
        is_samurai_monk = is_monk and not is_brotherhood
        is_shugenja = self.pc.has_tag('shugenja')
        is_bushi = self.pc.has_tag('bushi')
        is_courtier = self.pc.has_tag('courtier')

        # SHUGENJA/BUSHI/MONK SHEET
        if is_shugenja:
            self.write_pdf( 'sheet_shugenja.pdf', exporters.FDFExporterShugenja() )
        elif is_bushi or is_samurai_monk:
            self.write_pdf( 'sheet_bushi.pdf', exporters.FDFExporterBushi() )
        elif is_monk:
            self.write_pdf( 'sheet_monk.pdf', exporters.FDFExporterMonk() )
        if is_courtier:
            self.write_pdf( 'sheet_courtier.pdf', exporters.FDFExporterCourtier() )

        # SPELLS
        # we use as many extra spells sheet as needed

        if is_shugenja:
            spell_count  = len( self.pc.get_spells() )
            spell_offset = 0

            while spell_count > 0:
                _exporter = exporters.FDFExporterSpells( spell_offset )
                self.write_pdf( 'sheet_spells.pdf', _exporter )
                spell_offset += _exporter.spell_per_page
                spell_count  -= _exporter.spell_per_page

        if False: # DISABLED FOR NOW
            # DEDICATED SKILL SHEET
            skill_count  = len( self.pc.get_skills() )
            skill_offset = 0

            while skill_count > 0:
                _exporter = exporters.FDFExporterSkills( skill_offset )
                self.write_pdf( 'sheet_skill.pdf', _exporter )
                skill_offset += _exporter.skills_per_page
                skill_count  -= _exporter.skills_per_page

        # WEAPONS
        if len(self.pc.weapons) > 2:
            self.write_pdf( 'sheet_weapons.pdf', exporters.FDFExporterWeapons() )

        self.commit_pdf_export( export_file )

    def remove_advancement_item(self, adv_itm):
        if adv_itm in self.pc.advans:
            self.pc.advans.remove(adv_itm)
            self.update_from_model()

    def increase_trait(self, attrib):
        cur_value = self.pc.get_attrib_rank( attrib )
        new_value = cur_value + 1
        ring_id = models.get_ring_id_from_attrib_id(attrib)
        ring_nm = models.ring_name_from_id(ring_id)
        cost = self.pc.get_attrib_cost( attrib ) * new_value
        if self.pc.has_rule('elem_bless_%s' % ring_nm):
            cost -= 1
        text = models.attrib_name_from_id(attrib).capitalize()
        adv = models.AttribAdv(attrib, cost)
        adv.desc = (self.tr('{0}, Rank {1} to {2}. Cost: {3} xp')
                   .format( text, cur_value, new_value, adv.cost ))

        if (adv.cost + self.pc.get_px()) > self.pc.exp_limit:
            return CMErrors.NOT_ENOUGH_XP

        self.pc.add_advancement( adv )
        self.update_from_model()

        return CMErrors.NO_ERROR

    def increase_void(self):
        cur_value = self.pc.get_ring_rank( models.RINGS.VOID )
        new_value = cur_value + 1
        cost = self.pc.void_cost * new_value
        if self.pc.has_rule('enlightened'):
            cost -= 2
        adv = models.VoidAdv(cost)
        adv.desc = (self.tr('Void Ring, Rank {0} to {1}. Cost: {2} xp')
                   .format( cur_value, new_value, adv.cost ))
        if (adv.cost + self.pc.get_px()) > self.pc.exp_limit:
            return CMErrors.NOT_ENOUGH_XP

        self.pc.add_advancement( adv )
        self.update_from_model()

        return CMErrors.NO_ERROR

    def set_exp_limit(self, val):
        self.pc.exp_limit = val
        self.update_from_model()

    def set_health_multiplier(self, val):
        self.pc.health_multiplier = val
        self.update_from_model()

    def damage_health(self, val):
        self.pc.wounds += val
        if self.pc.wounds < 0: self.pc.wounds = 0
        if self.pc.wounds > self.pc.get_max_wounds():
            self.pc.wounds = self.pc.get_max_wounds()

        self.update_from_model()

    def buy_next_skill_rank(self, skill_id):
        print('buy skill rank {0}'.format(skill_id))
        cur_value = self.pc.get_skill_rank(skill_id)
        new_value = cur_value + 1

        cost    = new_value
        skill   = dal.query.get_skill(self.dstore, skill_id)
        sk_type = skill.type
        text    = skill.name

        if (self.pc.has_rule('obtuse') and
            sk_type == 'high' and
            skill_id != 'investigation'   and # investigation
            skill_id != 'medicine'):     # medicine

            # double the cost for high skill
            # other than medicine and investigation
            cost *= 2

        adv = models.SkillAdv(skill_id, cost)
        adv.rule = dal.query.get_mastery_ability_rule(self.dstore, skill_id, new_value)
        adv.desc = (self.tr('{0}, Rank {1} to {2}. Cost: {3} xp')
                   .format( text, cur_value, new_value, adv.cost ))


        if adv.cost + self.pc.get_px() > self.pc.exp_limit:
            return CMErrors.NOT_ENOUGH_XP

        self.pc.add_advancement(adv)
        self.update_from_model()

        return CMErrors.NO_ERROR

    def memo_spell(self, spell_id):
        print('memorize spell {0}'.format(spell_id))
        info_ = dal.query.get_spell(self.dstore, spell_id)
        cost  = info_.mastery
        text  = info_.name

        adv = models.MemoSpellAdv(spell_id, cost)
        adv.desc = (self.tr('{0}, Mastery {1}. Cost: {2} xp')
                   .format( text, cost, adv.cost ))

        if adv.cost + self.pc.get_px() > self.pc.exp_limit:
            return CMErrors.NOT_ENOUGH_XP

        self.pc.add_advancement(adv)
        self.update_from_model()

        return CMErrors.NO_ERROR

    def remove_spell(self, spell_id):
        self.pc.remove_spell(spell_id)
        self.update_from_model()

    def buy_school_requirements(self):
        for skill_uuid in self.get_missing_school_requirements():
            print('buy requirement skill {0}'.format(skill_uuid))
            if self.buy_next_skill_rank(skill_uuid) != CMErrors.NO_ERROR:
                return

    def check_if_tech_available(self):
        school = dal.query.get_school(self.dstore, self.pc.get_school_id())
        if school:
            count  = len(school.techs)
            print('check_if_tech_available', school.id, count, self.pc.get_school_rank())
            return count >= self.pc.get_school_rank()
        return False

    def check_tech_school_requirements(self):
        # one should have at least one rank in all school skills
        # in order to gain a school techniques
        return len(self.get_missing_school_requirements()) == 0

    def get_missing_school_requirements(self):
        list_     = []
        school_id = self.pc.get_school_id()
        school = dal.query.get_school(self.dstore, school_id)
        if school:
            print('check requirement for school {0}'.format(school_id))
            for sk in school.skills:
                print('needed {0}, got rank {1}'.format(sk.id, self.pc.get_skill_rank(sk.id)))
                if self.pc.get_skill_rank(sk.id) < 1:
                    list_.append(sk.id)
        return list_

    def set_pc_affinity(self, affinity):
        if self.pc.has_tag('chuda shugenja school'):
            self.pc.set_affinity('maho ' + affinity.lower())
            self.pc.set_deficiency(affinity.lower())
        else:
            self.pc.set_affinity(affinity.lower())
        self.update_from_model()

    def set_pc_deficiency(self, deficiency):
        self.pc.set_deficiency(deficiency.lower())
        self.update_from_model()

    def import_data_packs(self, data_pack_file):

        imported = 0

        for dp in data_pack_file:
            if self.import_data_pack(dp):
                imported += 1

        if imported > 0:
            self.reload_data()
            self.advise_successfull_import( imported )
        else:
            self.advise_error(self.tr("Cannot import data pack."))

    def import_data_pack(self, data_pack_file):
        try:
            dal.dataimport.CM_VERSION = APP_VERSION
            pack = dal.dataimport.DataPack(data_pack_file)
            if not pack.good():
                self.advise_error(self.tr("Invalid data pack."))
            else:
                dest = osutil.get_user_data_path()
                if pack.id == 'core':
                    dest = os.path.join(dest, 'core.data')
                elif pack.language:
                    dest = os.path.join(dest, 'data.' + pack.language)
                else:
                    dest = os.path.join(dest, 'data')

                pack.export_to  (dest)
            return True
        except Exception as e:
            return False

    def update_data_blacklist(self):
        self.data_pack_blacklist = [ x.id for x in self.dstore.packs if x.active == False ]
        settings = QtCore.QSettings()
        settings.setValue('data_pack_blacklist', self.data_pack_blacklist)

    def please_donate(self):
        donate_url = QtCore.QUrl("https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=Q87Q5BVS3ZKTE&lc=US&item_name=Daniele%20Simonetti&item_number=l5rcm_donate&currency_code=EUR&bn=PP%2dDonationsBF%3abtn_donate_SM%2egif%3aNonHosted")
        QtGui.QDesktopServices.openUrl(donate_url)

    def buy_kata(self, kata):
        adv = models.KataAdv(kata.id, kata.id, kata.mastery)
        adv.desc = self.tr('{0}, Cost: {1} xp').format( kata.name, adv.cost )

        if (adv.cost + self.pc.get_px()) > self.pc.exp_limit:
            return CMErrors.NOT_ENOUGH_XP

        self.pc.add_advancement( adv )
        self.update_from_model()

        return CMErrors.NO_ERROR

    def pc_is_monk(self):
        # is monk ?
        monk_schools        = [ x for x in self.pc.schools if x.has_tag('monk') ]
        is_monk             = len(monk_schools) > 0
        # is brotherhood monk?
        brotherhood_schools = [ x for x in monk_schools if x.has_tag('brotherhood') ]
        is_brotherhood      = len(brotherhood_schools) > 0

        # a friend of the brotherhood pay the same as the brotherhood members
        is_brotherhood = is_brotherhood or self.pc.has_rule('friend_brotherhood')

        return is_monk, is_brotherhood

    def pc_is_ninja(self):
        # is ninja?
        ninja_schools       = [ x for x in self.pc.schools if x.has_tag('ninja') ]
        is_ninja            = len(ninja_schools) > 0
        return is_ninja

    def pc_is_shugenja(self):
        # is shugenja?
        shugenja_schools    = [ x for x in self.pc.schools if x.has_tag('shugenja') ]
        is_shugenja         = len(shugenja_schools) > 0
        return is_shugenja

    def calculate_kiho_cost(self, kiho):

        # tattoos are free as long as you're eligible
        if 'tattoo' in kiho.tags: return 0

        cost_mult           = 1

        is_monk, is_brotherhood = self.pc_is_monk    ()
        is_ninja                = self.pc_is_ninja   ()
        is_shugenja             = self.pc_is_shugenja()

        if is_brotherhood:
            cost_mult = 1 # 1px / mastery
        elif is_monk:
            cost_mult = 1.5
        elif is_shugenja:
            cost_mult = 2
        elif is_ninja:
            cost_mult = 2

        return int(ceil(kiho.mastery*cost_mult))

    def check_kiho_eligibility(self, kiho):
        # check eligibility
        against_mastery     = 0

        is_monk, is_brotherhood = self.pc_is_monk    ()
        is_ninja                = self.pc_is_ninja   ()
        is_shugenja             = self.pc_is_shugenja()

        school_bonus        = 0
        relevant_ring       = models.ring_from_name(kiho.element)
        ring_rank           = self.pc.get_ring_rank(relevant_ring)

        if is_ninja:
            ninja_schools = [ x for x in self.pc.schools if x.has_tag('ninja') ]
            ninja_rank    = sum( [x.school_rank for x in ninja_schools ] )

        if is_monk:
            monk_schools = [ x for x in self.pc.schools if x.has_tag('monk') ]
            school_bonus = sum( [x.school_rank for x in monk_schools ] )

        against_mastery = school_bonus + ring_rank

        if is_brotherhood:
            return against_mastery >= kiho.mastery
        elif is_monk:
            return against_mastery >= kiho.mastery
        elif is_shugenja:
            return ring_rank >= kiho.mastery
        elif is_ninja:
            return ninja_rank >= kiho.mastery

        return False

    def buy_kiho(self, kiho):
        adv = models.KihoAdv(kiho.id, kiho.id, self.calculate_kiho_cost(kiho))
        adv.desc = self.tr('{0}, Cost: {1} xp').format( kiho.name, adv.cost )

        # monks can get free kihos
        if self.pc.get_free_kiho_count() > 0:
            adv.cost = 0
            self.pc.set_free_kiho_count( self.pc.get_free_kiho_count() - 1 )
            print('remaing free kihos', self.pc.get_free_kiho_count())

        if (adv.cost + self.pc.get_px()) > self.pc.exp_limit:
            return CMErrors.NOT_ENOUGH_XP

        self.pc.add_advancement( adv )
        self.update_from_model()

        return CMErrors.NO_ERROR

    def buy_tattoo(self, kiho):
        adv = models.KihoAdv(kiho.id, kiho.id, 0)
        adv.desc = self.tr('{0} Tattoo').format( kiho.name )

        self.pc.add_advancement( adv )
        self.update_from_model()

        return CMErrors.NO_ERROR

    def get_higher_tech(self):
        mt = None
        ms = None
        for t in self.pc.get_techs():
            school, tech = dal.query.get_tech(self.dstore, t)
            if not mt or tech.rank > mt.rank:
                ms, mt = school, tech
        return ms, mt

    def get_higher_tech_in_current_school(self):
        mt = None
        ms = None

        for t in self.pc.get_techs():
            school, tech = dal.query.get_tech(self.dstore, t)
            if school.id != self.pc.get_school_id(): continue
            if not mt or tech.rank > mt.rank:
                ms, mt = school, tech
        return ms, mt

    def get_character_full_name(self):

        # if the character has a family name
        # prepend the character name with it
        # e.g. Hida Hiroshi
        # otherwise just 'Hiroshi' will do

        family_name = ""
        family_obj = dal.query.get_family( self.dstore, self.pc.family )
        if family_obj:
            family_name = family_obj.name
            return "{} {}".format( family_name, self.pc.name )
        return self.pc.name

    def get_prev_and_next_school(self):

        all_schools = [ dal.query.get_school( self.dstore, x.school_id ) for x in self.pc.schools ]
        print('character schools: ', [ x.id for x in all_schools ])

        #if len(all_schools) == 0:
        #    return None, None
        #if len(all_schools) == 1:
        #    return None, all_schools[0]
        #return all_schools[-2], all_schools[-1]

        if len(all_schools) == 0:
            return None, None
        #if len(all_schools) == 1:
        #    return None, all_schools[0]

        last_learned_tech = None
        prev_school       = None
        if len( self.pc.get_techs() ) > 0:
            last_learned_tech = self.pc.get_techs() [ -1 ]
            prev_school, tech = dal.query.get_tech( self.dstore, last_learned_tech )

        return prev_school, all_schools[-1]

    def get_next_rank_in_school(self, school):

        out_tech = dal.query.get_school_tech( school, 1 )

        for t in sorted( school.techs, key = lambda x: x.rank ):
            if t.id not in self.pc.get_techs():
                return t
        return None



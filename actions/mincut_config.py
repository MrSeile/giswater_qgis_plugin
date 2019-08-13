"""
This file is part of Giswater 3
The program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the License,
or (at your option) any later version.
"""
# -*- coding: utf-8 -*-
try:
    from qgis.core import Qgis
except ImportError:
    from qgis.core import QGis as Qgis

if Qgis.QGIS_VERSION_INT < 29900:
    from qgis.PyQt.QtGui import QStringListModel
else:
    from qgis.PyQt.QtCore import QStringListModel

from qgis.PyQt.QtCore import Qt, QDate
from qgis.PyQt.QtWidgets import QTableView, QMenu, QPushButton, QLineEdit, QCompleter, QAbstractItemView
from qgis.PyQt.QtSql import QSqlTableModel

import datetime
import os
import subprocess
from functools import partial

from .. import utils_giswater
from ..ui_manager import Multirow_selector
from ..ui_manager import Multi_selector
from ..ui_manager import Mincut_edit
from .parent import ParentAction


class MincutConfig(ParentAction):
    
    def __init__(self, mincut):
        """ Class constructor """

        self.mincut = mincut
        self.canvas = mincut.canvas
        self.plugin_dir = mincut.plugin_dir
        self.controller = self.mincut.controller
        self.schema_name = self.controller.schema_name
        self.settings = self.mincut.settings
        

    def mg_mincut_management(self):
        """ Button 27: Mincut management """

        self.action = "mg_mincut_management"

        # Create the dialog and signals
        self.dlg_min_edit = Mincut_edit()
        self.load_settings(self.dlg_min_edit)
        self.set_dates()
        # self.set_dates_from_to(self.dlg_min_edit.date_to, self.dlg_min_edit.date_to, 'v_ui_anl_mincut_result_cat',
        #                        'forecast_start', 'forecast_end')
        self.dlg_min_edit.date_from.setEnabled(False)
        self.dlg_min_edit.date_to.setEnabled(False)
        self.set_icon(self.dlg_min_edit.btn_selector_mincut, "191")
        self.set_icon(self.dlg_min_edit.btn_show, "191")

        self.tbl_mincut_edit = self.dlg_min_edit.findChild(QTableView, "tbl_mincut_edit")
        self.txt_mincut_id = self.dlg_min_edit.findChild(QLineEdit, "txt_mincut_id")
        self.tbl_mincut_edit.setSelectionBehavior(QAbstractItemView.SelectRows)        
        
        # Adding auto-completion to a QLineEdit
        self.completer = QCompleter()
        self.txt_mincut_id.setCompleter(self.completer)
        model = QStringListModel()

        sql = "SELECT DISTINCT(id) FROM v_ui_anl_mincut_result_cat "
        rows = self.controller.get_rows(sql)
        values = []
        if rows:
            for row in rows:
                values.append(str(row[0]))

        model.setStringList(values)
        self.completer.setModel(model)
        self.txt_mincut_id.textChanged.connect(partial(self.filter_by_id, self.tbl_mincut_edit))
        self.dlg_min_edit.date_from.dateChanged.connect(partial(self.filter_by_id, self.tbl_mincut_edit))
        self.dlg_min_edit.date_to.dateChanged.connect(partial(self.filter_by_id, self.tbl_mincut_edit))
        self.dlg_min_edit.cmb_expl.currentIndexChanged.connect(partial(self.filter_by_id, self.tbl_mincut_edit))
        self.dlg_min_edit.spn_next_days.setRange(-9999, 9999)
        self.dlg_min_edit.btn_next_days.clicked.connect(self.filter_by_days)
        self.dlg_min_edit.spn_next_days.valueChanged.connect(self.filter_by_days)
        self.dlg_min_edit.btn_show.clicked.connect(self.show_selection)
        self.dlg_min_edit.btn_cancel_mincut.clicked.connect(self.set_state_cancel_mincut)
        self.dlg_min_edit.tbl_mincut_edit.doubleClicked.connect(self.open_mincut)
        self.dlg_min_edit.btn_cancel.clicked.connect(partial(self.close_dialog, self.dlg_min_edit))
        self.dlg_min_edit.rejected.connect(partial(self.close_dialog, self.dlg_min_edit))
        self.dlg_min_edit.btn_delete.clicked.connect(partial(self.delete_mincut_management, self.tbl_mincut_edit, "v_ui_anl_mincut_result_cat", "id"))
        self.dlg_min_edit.btn_selector_mincut.clicked.connect(self.mincut_selector)
        self.btn_notify = self.dlg_min_edit.findChild(QPushButton, "btn_notify")
        self.btn_notify.clicked.connect(partial(self.get_clients_codes, self.dlg_min_edit.tbl_mincut_edit))
        self.set_icon(self.btn_notify, "307")

        btn_visible = self.settings.value('customized_actions/show_mincut_sms', 'FALSE')
        self.btn_notify.setVisible(True) if btn_visible.upper() == 'TRUE' else self.btn_notify.setVisible(False)

        self.populate_combos()
        self.dlg_min_edit.state_edit.activated.connect(partial(self.filter_by_id, self.tbl_mincut_edit))

        # Set a model with selected filter. Attach that model to selected table
        self.fill_table_mincut_management(self.tbl_mincut_edit, self.schema_name + ".v_ui_anl_mincut_result_cat")
        self.set_table_columns(self.dlg_min_edit, self.tbl_mincut_edit, "v_ui_anl_mincut_result_cat")

        #self.mincut.set_table_columns(self.tbl_mincut_edit, "v_ui_anl_mincut_result_cat")

        # Open the dialog
        self.dlg_min_edit.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.dlg_min_edit.show()


    def get_clients_codes(self, qtable):

        selected_list = qtable.selectionModel().selectedRows()
        if len(selected_list) == 0:
            message = "Any record selected"
            self.controller.show_warning(message)
            return

        inf_text = "Are you sure you want to send smd to this clients?"
        for i in range(0, len(selected_list)):
            row = selected_list[i].row()
            id_ = qtable.model().record(row).value(str('id'))
            inf_text += "\n\nMincut: " + str(id_) + ""
            sql = ("SELECT code, t2.forecast_start, t2.forecast_end, t2.mincut_type "
                   "FROM " + self.schema_name + ".anl_mincut_result_hydrometer AS t1 "
                   "JOIN " + self.schema_name + ".ext_rtc_hydrometer ON t1.hydrometer_id::bigint = ext_rtc_hydrometer.id::bigint "
                   "JOIN " + self.schema_name + ".anl_mincut_result_cat as t2 ON t1.result_id = t2.id "
                   "WHERE result_id = " + str(id_))

            rows = self.controller.get_rows(sql, commit=True, log_sql=True)
            if not rows:
                inf_text += "\nClients: None(No messages will be sent)"
                continue

            inf_text += "\nClients: \n"
            for row in rows:
                inf_text += str(row[0]) + ", "

        inf_text = inf_text[:-2]
        inf_text += "\n"
        answer = self.controller.ask_question(str(inf_text))
        if answer:
            self.call_sms_script(qtable)


    def call_sms_script(self, qtable):
        path = self.settings.value('customized_actions/path_sms_script')
        if path is None or not os.path.exists(path):
            self.controller.show_warning("File not found", parameter=path)
            return

        selected_list = qtable.selectionModel().selectedRows()
        list_mincut_id = []
        for i in range(0, len(selected_list)):
            row = selected_list[i].row()
            id_ = qtable.model().record(row).value(str('id'))
            sql = ("SELECT code, t2.forecast_start, t2.forecast_end, t2.mincut_type, notified "
                   "FROM " + self.schema_name + ".anl_mincut_result_hydrometer AS t1 "
                   "JOIN " + self.schema_name + ".ext_rtc_hydrometer ON t1.hydrometer_id::bigint = ext_rtc_hydrometer.id::bigint "
                   "JOIN " + self.schema_name + ".anl_mincut_result_cat as t2 ON t1.result_id = t2.id "
                   "WHERE result_id = " + str(id_))

            rows = self.controller.get_rows(sql, commit=True, log_sql=True)
            if not rows:
                print("NOT ROWS")
                continue

            from_date = str(rows[0][1].strftime('%d/%m/%Y %H:%M'))
            to_date = str(rows[0][2].strftime('%d/%m/%Y %H:%M'))
            _type = rows[0][3]
            list_clients = []
            list_mincut_id.append(id_)
            for row in rows:
                client = str(row[0])
                list_clients.append(client)

            status_code = subprocess.call(['python', path, _type, from_date, to_date, list_clients])
            _date_sended = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
            sql = ("UPDATE " + self.schema_name + ".anl_mincut_result_cat ")
            print(row[4])
            if row[4] is None:
                sql += ("SET notified = ('[{\"code\":\""+str(status_code)+"\",\"date\":\""+str(_date_sended)+"\"}]') ")
            else:
                sql += ("SET notified= concat(replace(notified::text,']',','),'{\"code\":\""+str(status_code)+"\",\"date\":\""+str(_date_sended)+"\"}]')::json ")
            sql += ("WHERE id = '"+str(id_)+"'")
            row = self.controller.execute_sql(sql, commit=True, log_sql=True)

            # Set a model with selected filter. Attach that model to selected table
            self.fill_table_mincut_management(self.tbl_mincut_edit, self.schema_name + ".v_ui_anl_mincut_result_cat")
            self.set_table_columns(self.dlg_min_edit, self.tbl_mincut_edit, "v_ui_anl_mincut_result_cat")


    def set_state_cancel_mincut(self):

        selected_list = self.tbl_mincut_edit.selectionModel().selectedRows()
        if len(selected_list) == 0:
            message = "Any record selected"
            self.controller.show_warning(message)
            return
        inf_text = ""
        list_id = ""
        for i in range(0, len(selected_list)):
            row = selected_list[i].row()
            id_ = self.tbl_mincut_edit.model().record(row).value("id")
            inf_text += str(id_)+", "
            list_id = list_id+"'"+str(id_)+"', "
        inf_text = inf_text[:-2]
        list_id = list_id[:-2]
        msg = "Are you sure you want to cancel these mincuts?"
        title = "Cancel mincuts"
        answer = self.controller.ask_question(msg, title, inf_text)
        if answer:
            sql = ("UPDATE anl_mincut_result_cat SET mincut_state = 3 "
                   " WHERE id::text IN ("+list_id+")")
            self.controller.execute_sql(sql, log_sql=False)
            self.tbl_mincut_edit.model().select()


    def show_selection(self):

        selected_list = self.tbl_mincut_edit.selectionModel().selectedRows()
        if len(selected_list) == 0:
            message = "Any record selected"
            self.controller.show_warning(message)
            return

        sql = ("DELETE FROM anl_mincut_result_selector WHERE cur_user = current_user;")
        for i in range(0, len(selected_list)):
            row = selected_list[i].row()
            id_ = self.tbl_mincut_edit.model().record(row).value("id")
            sql += ("\nINSERT INTO anl_mincut_result_selector (cur_user, result_id) "
                    "  VALUES(current_user, " + str(id_) + ");")
        status = self.controller.execute_sql(sql)
        if not status:
            message = "Error updating table"
            self.controller.show_warning(message, parameter='anl_mincut_result_selector')
        self.mincut.set_visible_mincut_layers(True)


    def populate_combos(self):

        # Fill ComboBox state
        sql = ("SELECT name"
               " FROM anl_mincut_cat_state"
               " ORDER BY name")
        rows = self.controller.get_rows(sql)
        utils_giswater.fillComboBox(self.dlg_min_edit, "state_edit", rows)

        sql = ("SELECT expl_id, name FROM exploitation ORDER BY name")
        rows = self.controller.get_rows(sql, log_sql=False, add_empty_row=True)
        utils_giswater.set_item_data(self.dlg_min_edit.cmb_expl, rows, 1)


    def mincut_selector(self):

        self.dlg_mincut_sel = Multirow_selector()
        self.load_settings(self.dlg_mincut_sel)

        self.dlg_mincut_sel.btn_ok.clicked.connect(partial(self.close_dialog, self.dlg_mincut_sel))
        self.dlg_mincut_sel.rejected.connect(partial(self.close_dialog, self.dlg_mincut_sel))
        self.dlg_mincut_sel.setWindowTitle("Mincut selector")
        utils_giswater.setWidgetText(self.dlg_mincut_sel, 'lbl_filter', self.controller.tr('Filter by: Mincut id', context_name='labels'))
        utils_giswater.setWidgetText(self.dlg_mincut_sel, 'lbl_unselected', self.controller.tr('Unselected mincut', context_name='labels'))
        utils_giswater.setWidgetText(self.dlg_mincut_sel, 'lbl_selected', self.controller.tr('Selected mincut', context_name='labels'))

        tableleft = "v_ui_anl_mincut_result_cat"
        tableright = "anl_mincut_result_selector"
        field_id_left = "id"
        field_id_right = "result_id"
        hide_left = [0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
        self.multi_row_selector(self.dlg_mincut_sel, tableleft, tableright, field_id_left, field_id_right, hide_left=hide_left)
        self.dlg_mincut_sel.btn_select.clicked.connect(partial(self.mincut.set_visible_mincut_layers))

        # Open dialog
        self.open_dialog(self.dlg_mincut_sel, maximize_button=False)


    def open_mincut(self):
        """ Open mincut form with selected record of the table """

        selected_list = self.tbl_mincut_edit.selectionModel().selectedRows()
        if len(selected_list) == 0:
            message = "Any record selected"
            self.controller.show_warning(message)
            return
        
        row = selected_list[0].row()

        # Get mincut_id from selected row
        result_mincut_id = self.tbl_mincut_edit.model().record(row).value("id")

        # Close this dialog and open selected mincut
        self.close_dialog(self.dlg_min_edit)
        self.mincut.is_new = False
        self.mincut.init_mincut_form()
        self.mincut.load_mincut(result_mincut_id)


    def filter_by_days(self):

        date_from = datetime.datetime.now()
        days_added = self.dlg_min_edit.spn_next_days.text()
        date_to = datetime.datetime.now()
        date_to += datetime.timedelta(days=int(days_added))

        # If the date_to is less than the date_from, you have to exchange them or the interval will not work
        if date_to < date_from:
            aux = date_from
            date_from = date_to
            date_to = aux

        format_low = '%Y-%m-%d 00:00:00.000'
        format_high = '%Y-%m-%d 23:59:59.999'
        interval = "'{}'::timestamp AND '{}'::timestamp".format(
            date_from.strftime(format_low), date_to.strftime(format_high))

        expr = "(forecast_start BETWEEN {0})".format(interval)
        self.controller.log_info(str(expr))
        self.tbl_mincut_edit.model().setFilter(expr)
        self.tbl_mincut_edit.model().select()


    def filter_by_id(self, qtable):

        expr = ""
        id_ = utils_giswater.getWidgetText(self.dlg_min_edit, self.dlg_min_edit.txt_mincut_id, False, False)
        state = utils_giswater.getWidgetText(self.dlg_min_edit, self.dlg_min_edit.state_edit, False, False)
        expl = utils_giswater.get_item_data(self.dlg_min_edit, self.dlg_min_edit.cmb_expl, 0)
        dates_filter = ""
        if state == '':
            self.dlg_min_edit.date_from.setEnabled(False)
            self.dlg_min_edit.date_to.setEnabled(False)
        else:
            self.dlg_min_edit.date_from.setEnabled(True)
            self.dlg_min_edit.date_to.setEnabled(True)

            # Get selected dates
            visit_start = self.dlg_min_edit.date_from.date()
            visit_end = self.dlg_min_edit.date_to.date()
            date_from = visit_start.toString('yyyyMMdd 00:00:00')
            print(type(date_from))
            self.controller.log_info(str(date_from))
            date_to = visit_end.toString('yyyyMMdd 23:59:59')
            if date_from > date_to:
                message = "Selected date interval is not valid"
                self.controller.show_warning(message)
                return

            # Create interval dates
            format_low = 'yyyy-MM-dd 00:00:00.000'
            format_high = 'yyyy-MM-dd 23:59:59.999'
            interval = "'{}'::timestamp AND '{}'::timestamp".format(
                visit_start.toString(format_low), visit_end.toString(format_high))
            if state in 'Planified':
                utils_giswater.setWidgetText(self.dlg_min_edit, self.dlg_min_edit.lbl_date_from, 'Date from: forecast_start')
                utils_giswater.setWidgetText(self.dlg_min_edit, self.dlg_min_edit.lbl_date_to, 'Date to: forecast_end')
                dates_filter = ("AND (forecast_start BETWEEN {0}) AND (forecast_end BETWEEN {0})".format(interval))
            elif state in ('In Progress', 'Finished'):
                utils_giswater.setWidgetText(self.dlg_min_edit, self.dlg_min_edit.lbl_date_from, 'Date from: exec_start')
                utils_giswater.setWidgetText(self.dlg_min_edit, self.dlg_min_edit.lbl_date_to, 'Date to: exec_end')
                dates_filter = ("AND (exec_start BETWEEN {0}) AND (exec_end BETWEEN {0})".format(interval))
            else:
                utils_giswater.setWidgetText(self.dlg_min_edit, self.dlg_min_edit.lbl_date_from, 'Date from:')
                utils_giswater.setWidgetText(self.dlg_min_edit, self.dlg_min_edit.lbl_date_to, 'Date to:')
        expr += " (id::text ILIKE '%" + id_ + "%'"
        expr += " OR work_order::text ILIKE '%" + id_ + "%' OR work_order IS null)"
        expr += " " + dates_filter + ""
        if state != '':
            expr += " AND state::text ILIKE '%" + state + "%' OR state IS null"
        expr += " AND expl_id::text ILIKE '%" + str(expl) + "%' OR expl_id IS null"
        self.controller.log_info(str(expr))
        # Refresh model with selected filter
        qtable.model().setFilter(expr)
        qtable.model().select()


    def fill_table_mincut_management(self, widget, table_name):
        """ Set a model with selected filter. Attach that model to selected table """

        # Set model
        model = QSqlTableModel()
        model.setTable(table_name)
        model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        model.sort(0, 1)
        model.select()

        # Check for errors
        if model.lastError().isValid():
            self.controller.show_warning(model.lastError().text())

        # Attach model to table view
        widget.setModel(model)


    def delete_mincut_management(self, widget, table_name, column_id):
        """ Delete selected elements of the table (by id) """
        
        # Get selected rows
        selected_list = widget.selectionModel().selectedRows()
        if len(selected_list) == 0:
            message = "Any record selected"
            self.controller.show_warning(message)
            return

        inf_text = ""
        list_id = ""
        for i in range(0, len(selected_list)):
            row = selected_list[i].row()
            id_ = widget.model().record(row).value(str(column_id))
            inf_text+= str(id_) + ", "
            list_id = list_id + "'" + str(id_) + "', "
        inf_text = inf_text[:-2]
        list_id = list_id[:-2]
        message = "Are you sure you want to delete these records?"
        title = "Delete records"
        answer = self.controller.ask_question(message, title, inf_text)
        if answer:
            sql = ("DELETE FROM " + table_name + ""
                   " WHERE " + column_id + " IN (" + list_id + ")")
            self.controller.execute_sql(sql)
            widget.model().select()
            layer = self.controller.get_layer_by_tablename('v_anl_mincut_result_node')
            if layer is not None:
                layer.triggerRepaint()
            layer = self.controller.get_layer_by_tablename('v_anl_mincut_result_connec')
            if layer is not None:
                layer.triggerRepaint()
            layer = self.controller.get_layer_by_tablename('v_anl_mincut_result_arc')
            if layer is not None:
                layer.triggerRepaint()
            layer = self.controller.get_layer_by_tablename('v_anl_mincut_result_valve')
            if layer is not None:
                layer.triggerRepaint()
            layer = self.controller.get_layer_by_tablename('v_anl_mincut_result_cat')
            if layer is not None:
                layer.triggerRepaint()
            layer = self.controller.get_layer_by_tablename('v_anl_mincut_result_hydrometer')
            if layer is not None:
                layer.triggerRepaint()


    def set_dates(self):

        sql = ("SELECT MIN(LEAST(forecast_start, exec_start)), MAX(GREATEST(forecast_end, exec_end))"
               " FROM {}".format('v_ui_anl_mincut_result_cat'))
        row = self.controller.get_row(sql, log_sql=True)
        if row:
            if row[0]:
                self.dlg_min_edit.date_from.setDate(row[0])
            else:
                current_date = QDate.currentDate()
                self.dlg_min_edit.date_from.setDate(current_date)
            if row[1]:
                self.dlg_min_edit.date_to.setDate(row[1])
            else:
                current_date = QDate.currentDate()
                self.dlg_min_edit.date_to.setDate(current_date)
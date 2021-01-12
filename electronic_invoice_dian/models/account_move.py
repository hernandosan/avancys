# -*- coding: utf-8 -*-
import base64
from email.utils import parseaddr
import operator
import uuid
import logging
from functools import reduce
import qrcode
# import cStringIO
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import config
from datetime import datetime, timedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import requests
import json
import re
import os
from zipfile import ZipFile
from .http_helper import HEADERS
from .http_helper import INVOICE
from .http_helper import URL_XML
from . import xml_helper

# Constants

UTC_ADJUST = '-05:00'
UTC_TIME_CO = 5
HOUR_CHARS = 11
PRECISION = 2
EI_STATE_SELECTION = [
    ('pending', 'No Transferido'),
    ('done', 'Emitido'),
    ('exception', 'Excepción de Envio'),
    ('dian_reject', 'Rechazado DIAN'),
    ('dian_accept', 'Aceptado DIAN'),
    ('customer_reject', 'Rechazado Cliente'),
    ('customer_accept', 'Aceptado Cliente')
]
TAM_MAP_NAME = {
    '01': 'IVA',
    '02': 'IC',
    '03': 'ICA',
    '04': 'INC',
    '05': 'ReteIVA',
    '06': 'ReteFuente',
    '07': 'ReteICA'
}

# Warnings

WRONG_DB_MATCH_WARNING = """
No es posible generar la Factura Electrónica, verifique que la compañía tenga
habilitado el check de Facturación Electrónica y que la base de datos sea la correcta"""
ENV_MISSING_WARNING = """
Debe configurarse en la Compañía el tipo de Ambiente para Facturación Electrónica"""
OP_TYPE_MISSING_WARNING = """
Debe configurarse en la Compañía el Tipo de Operación"""
UNSUPPORTED_PDF_FORMAT_WARNING = """
Formato de pdf de factura electrónica no encontrado,
verifique la parametrizacion en la compañia.
"""
JOURNAL_RESOLUTION_ERROR = """
Error en la resolución del diario:
No se encontro ID de Resolución o Tipo de documento
"""
NO_CURRENCY_RATE_WARNING = """
No se encontró una tasa de cambio para la Fecha de la factura
"""
NO_REFERENCED_INVOICE_ERROR = """
No se encontró una factura electrónica a rectificar válida"""
UNACCEPTED_REFERENCE_ERROR = """
La factura electrónica a rectificar %s no tiene CUFE
"""
PDF_GENERATION_ERROR = """Hubo un error al generar el PDF de la factura"""
SEND_ERROR = """No fue posible enviar la factura al proovedor, error de conexión"""
PROVIDER_ERROR = """
Ha ocurrido un error al procesar la factura, por favor intente de nuevo"""
INVALID_EMAIL_ERROR = """No se encontró un email válido en el cliente"""
EMAIL_GENERATION_ERROR = """No se pudo generar email FE %s"""

# Logger

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    transaction_log_ids = fields.One2many(
        string='Logs', comodel_name='ei.transaction.log',
        inverse_name='invoice_id', copy=False)
    ei_state = fields.Selection(
        string='Estado FE', default='pending', readonly=True, copy=False,
        selection=EI_STATE_SELECTION)
    ei_cufe = fields.Char(
        string='CUFE', readonly=True, size=96, track_visibility='onchange',
        copy=False)
    ei_cude = fields.Char(
        string='CUDE', readonly=True, size=96, track_visibility='onchange',
        copy=False)
    ei_qr = fields.Char(string='Informacion QR', readonly=True, copy=False)
    ei_xml_content = fields.Text(string='Contenido XML', copy=False)
    ei_app_response = fields.Text(
        string='Contenido XML Application Response', copy=False)
    ei_email_sent = fields.Boolean(string='Email Enviado', copy=False)
    ei_generation_date = fields.Char(
        string='Hora de Generación', readonly=True, copy=False)
    ei_validation_date = fields.Char(
        string='Hora de Validacion', readonly=True, copy=False)

    # Acknowledgement management

    def _create_token(self):
        self.ensure_one()
        if not self.access_token:
            self.access_token = uuid.uuid4().hex

    def do_accept(self):
        if self.ei_state in ('customer_accept', 'customer_reject'):
            return False
        self.ei_state = 'customer_accept'
        return True

    def do_reject(self):
        if self.ei_state in ('customer_accept', 'customer_reject'):
            return False
        self.ei_state = 'customer_reject'
        return True

    # Log management

    def create_transaction_log(self, invoice, state, content, document_type='none'):
        self.env['ei.transaction.log'].create({
            'invoice_id': invoice.id,
            'date': datetime.now(),
            'document_state': state,
            'document_type': document_type,
            'content': content
        })

    # Invoice processing

    def action_post(self):
        company = self.mapped(lambda invoice: invoice.company_id)
        res = super(AccountMove, self).action_post()
        if company.ei_automatic_generation:
            self.generate_electronic_invoice()
        return res

    def _get_invoice_json(self, invoice):
        company = invoice.company_id
        company_partner = company.partner_id
        invoice_partner = invoice.partner_id
        journal = invoice.journal_id
        document_type = journal.resolution_id.document_type
        resolution = journal.resolution_id
        if (not resolution.id_param or not resolution.prefix or not document_type):
            self.create_transaction_log(
                invoice, 'exception', JOURNAL_RESOLUTION_ERROR)
            return False
        nowtime = datetime.now() - timedelta(hours=UTC_TIME_CO)
        generation_date_time = nowtime.strftime(
            DEFAULT_SERVER_DATETIME_FORMAT) + UTC_ADJUST
        invoice.ei_generation_date = generation_date_time
        generation_time = generation_date_time[HOUR_CHARS:]
        day_rate = self.env['res.currency.rate'].search([
            ('name', '=', invoice.invoice_date.strftime(DEFAULT_SERVER_DATE_FORMAT)),
            ('currency_id', '=', invoice.currency_id.id)
        ])
        if invoice.currency_id != company.currency_id and not day_rate:
            raise ValidationError(NO_CURRENCY_RATE_WARNING)
        currency_name = invoice.currency_id.name

        ncnd = "enabled" if document_type in ('91', '92') else "disabled"
        case_reference_invoice = {
            '91': invoice.reversed_entry_id,
            '92': invoice.debit_origin_id,
        }
        reference_invoice = case_reference_invoice.get(document_type, False)

        if ncnd == "enabled":
            if not reference_invoice:
                self.create_transaction_log(
                    invoice, 'exception', NO_REFERENCED_INVOICE_ERROR)
                return False
            if not reference_invoice.ei_cufe:
                self.create_transaction_log(
                    invoice, 'exception', UNACCEPTED_REFERENCE_ERROR % reference_invoice.name)
                return False

        datos_conexion = {
            "token": company.software_token,
            "documento": company_partner.ref_num,
            "dv": str(company_partner.verification_code),
            "id_cabecera": "0",
            "id_usuario": "1"
        }
        tipo_documento = {
            "numero": document_type
        }
        basicos_factura = {
            "consecutivo": invoice.name.replace(journal.resolution_id.prefix, ''),
            "moneda": currency_name,
            "tipo_operacion": company.ei_id_customization,
            "fecha_factura": invoice.invoice_date.strftime(DEFAULT_SERVER_DATE_FORMAT),
            "hora_factura": generation_time
        }
        respuesta = {
            "ruta_post": company.service_url_post,
            "ruta_get": company.service_url_get,
            "metodo": "ajax",
            "extra1": "",
            "extra2": ""
        }
        param_basico = {
            "id_param": str(journal.resolution_id.id_param),
            "test": "0",
            "ambiente": "1" if company.ei_environment == 'production' else "2",
            "ruta_to_soap": ("SendBillSync"
                             if company.ei_environment == 'production'
                             else "SendTestSetAsync")
        }
        facturador = {
            "ProviderID": company_partner.ref_num,
            "dv": str(company_partner.verification_code)
        }
        autorizacion_descarga = {
            "activo": "enabled",
            "numero_documento": "",
            "dv": "",
            "tipo_documento": company_partner.ref_type_id.code_dian
        }
        WithholdingTaxTotal = {
            "aplica": "0"
        }

        def validate_country_code(country_code):
            if country_code == '169':
                return 'CO'
            return str(country_code)

        def is_colombia(country_code):
            return country_code in ('169', 'CO')

        datos_empresa = {
            "Pais": validate_country_code(company_partner.country_id.code),
            "departamento": company_partner.state_id.code,
            "municipio": company_partner.state_id.code + company_partner.city_id.zipcode,
            "direccion": company_partner.street,
            "nombre_sucursal": company_partner.city_id.name or company_partner.name
        }
        partner_country = invoice_partner.country_id.code
        datos_cliente = {
            "tipo_persona": "1",
            "Pais": partner_country,
            "municipio": (str(invoice_partner.state_id.code)
                          + str(invoice_partner.city_id.zipcode)
                          if is_colombia(partner_country) else ""),
            "numero_documento": invoice_partner.ref_num,
            "dv": invoice_partner.verification_code,
            "tipo_documento": invoice_partner.ref_type_id.code_dian,
            "departamento": (invoice_partner.state_id.code
                             if is_colombia(partner_country) else ""),
            "direccion": (invoice_partner.street or "") + (invoice_partner.street2 or ""),
            "nombre_sucursal": "",
            "RUT_nombre": invoice_partner.name or 'Receptor',
            "RUT_pais": partner_country,
            "RUT_departamento": (company_partner.state_id.code
                                 if is_colombia(partner_country) else ""),
            "RUT_municipio": (str(invoice_partner.state_id.code)
                              + str(invoice_partner.city_id.zipcode)
                              if is_colombia(partner_country) else ""),
            "RUT_direcci\u00f3n": invoice_partner.street,
            "RUT_impuesto": "01",
            "Respon_fiscales": "",
            "Num_matricula_mercantil": "",
            "Nombre_contacto": invoice_partner.name,
            "Tel_contacto": invoice_partner.phone,
            "Correo_contacto": invoice_partner.email,
            "Nota_contacto": ""
        }
        datos_transportadora = {
            "active": "disabled",
            "tipo_persona": "1",
            "Pais": "",
            "municipio": "",
            "numero_documento": "",
            "dv": "",
            "tipo_documento": "",
            "departamento": "",
            "direccion": "",
            "nombre_sucursal": "",
            "RUT_nombre": "",
            "RUT_pais": "",
            "RUT_departamento": "",
            "RUT_municipio": "",
            "RUT_direcci\u00f3n": "",
            "RUT_impuesto": "",
            "Respon_fiscales": "",
            "Num_matricula_mercantil": "",
            "Nombre_contacto": "",
            "Tel_contacto": "",
            "Telfax_contacto": "",
            "Correo_contacto": "",
            "Nota_contacto": ""
        }
        QR = {
            "active": "enabled"
        }
        Periodo_pago = {
            "active": "disabled",
            "fecha_inicial": "",
            "fecha_final": ""
        }
        payment_term = sum(invoice.invoice_payment_term_id.line_ids.mapped(
            lambda line: line.days))
        Metodo_pago = {
            "active": "enabled",
            "codigo_metodo": "2" if payment_term else "1",
            "codigo_medio": "ZZZ",
            "fecha_vencimiento": (invoice.invoice_date_due.strftime(DEFAULT_SERVER_DATE_FORMAT)
                                  or invoice.invoice_date.strftime(DEFAULT_SERVER_DATE_FORMAT)),
            "identificacion_metodo": "Mutuo Acuerdo"
        }

        Referencia_factura = {
            "active": ncnd,
            "referencia_afectada": (reference_invoice.name if ncnd == "enabled" else ""),
            "cufe_cude": (reference_invoice.ei_cufe if ncnd == "enabled" else ""),
            "algoritm_cufe_cude": "CUFE-SHA384",
            "fecha_factura": (reference_invoice.invoice_date.strftime(DEFAULT_SERVER_DATE_FORMAT)
                              if ncnd == "enabled" else "")
        }
        Referencia_factura2 = {
            "active": "disabled",
            "referencia_afectada": "",
            "cufe_cude": "",
            "algoritm_cufe_cude": "",
            "fecha_factura": ""
        }
        respuesta_discrepancia = {
            "active": ncnd,
            "referencia": (reference_invoice.name
                           if ncnd == "enabled" else ""),
            "codigo": ("4" if document_type == '91'
                       else "6" if document_type == "92" else ""),
            "descripci\u00f3n_correccion": ""
        }
        order_de_referencia = {
            "active": "enabled" if 0 else "disabled",
            "codigo": "",
            "IssueDate": invoice.invoice_date.strftime(DEFAULT_SERVER_DATE_FORMAT),
        }
        Referencia_envio = {
            "active": "disabled",
            "id": ""
        }
        Referencia_recibido = {
            "active": "disabled",
            "id": ""
        }
        Terminos_de_entrega = {
            "active": "disabled",
            "terminos_Especiales": "",
            "cod_respo_perdida": ""
        }
        currency_rate = "enabled" if invoice.currency_id != company.currency_id else "disabled"
        currency_rate_val = day_rate.rate or 1.0
        Tasa_cambio = {
            "active": currency_rate,
            "Divisa_base": invoice.currency_id.name,
            "Divisa_a_convertir": company.currency_id.name,
            "Valor": str(currency_rate_val),
            "Fecha_conversion": invoice.invoice_date.strftime(DEFAULT_SERVER_DATE_FORMAT)
        }
        AdditionalDocumentReference = {
            "active": "disabled",
            "pre_consec": "",
            "fecha_creacion": "",
            "identificador": ""
        }
        Anticipos = [
            {
                "active": "disabled",
                "tipo_anticipo": "RED3123856",
                "valor_pago": "1000.00",
                "fecha_recibido": "2018-10-01",
                "fecha_realizado": "2018-09-29",
                "hora_realizado": "23:02:05",
                "instrucciones": "Prepago recibido"
            },
            {
                "active": "disabled",
                "tipo_anticipo": "RED3123857",
                "valor_pago": "850.00",
                "fecha_recibido": "2018-10-01",
                "fecha_realizado": "2018-09-29",
                "hora_realizado": "23:02:05",
                "instrucciones": "Prepago recibido"
            }
        ]

        Productos_servicios = []
        # Invoice lines
        for line in invoice.invoice_line_ids.filtered(
                lambda line: not line.exclude_from_invoice_tab):
            sample = line.discount == 100.0
            line_taxes = [
                [
                    tax.ei_code,
                    TAM_MAP_NAME.get(tax.ei_code, ''),
                    str(abs(round(tax.amount)))
                ] for tax in
                line.tax_ids if tax.ei_code == '01'
            ]
            taxes = reduce(operator.add, line_taxes or [0]) or []
            line_detail = {
                "active": "enabled",
                "Cantidad": str(line.quantity),
                "unidad_cantidad": str(line.product_uom_id.code_dian),
                "Costo_unidad": str(round(line.price_unit / currency_rate_val, PRECISION)),
                "Muestra": "Si" if sample else "No",
                "DeliveryLocation_active": ("enabled" if line.product_id.default_code
                                            else "disabled"),
                "DeliveryLocation_esq_id": "999",
                "DeliveryLocation_nombre": "",
                "DeliveryLocation_dato": line.product_id.default_code or "",
                "Codigo_muestra": "01" if sample else "0",
                "Desc_muestra": str(line.discount or 0.0),
                "Valor_muestra": (str(round(line.price_unit / currency_rate_val, PRECISION))
                                  if sample else "0"),
                "Descuento_cargo": "Credito",
                "ID_descuento_cargo": "11",
                "Porcentaje_descuento_cargo": "0.0" if sample else str(line.discount or 0.0),
                "Descripcion_descuento_cargo": "Otro descuento",
                "Mandatario": "",
                "Descripcion": line.product_id.name or "",
                "Prefijo_codigo_producto": "",
                "Codigo_producto": line.product_id.default_code or "",
                "Cantidad_x_paquete": "1",
                "Marca": "ninguna",
                "Modelo": "ninguna",
                "esquema_id": "",
                "esquema_dato": "",
                "esquema_name": "",
                "array_impuestos": taxes,
                "tributo_unidad": "0",
                "SellersItemIdentification_ID": "",
                "InformationContentProviderParty_ID": ""
            }
            Productos_servicios.append(line_detail)

        datafe = {
            "datos_conexion": datos_conexion,
            "tipo_documento": tipo_documento,
            "basicos_factura": basicos_factura,
            "respuesta": respuesta,
            "param_basico": param_basico,
            "facturador": facturador,
            "autorizacion_descarga": autorizacion_descarga,
            "WithholdingTaxTotal": WithholdingTaxTotal,
            "datos_empresa": datos_empresa,
            "datos_cliente": datos_cliente,
            "datos_transportadora": datos_transportadora,
            "QR": QR,
            "Periodo_pago": Periodo_pago,
            "Metodo_pago": Metodo_pago,
            "Referencia_factura": Referencia_factura,
            "Referencia_factura2": Referencia_factura2,
            "respuesta_discrepancia": respuesta_discrepancia,
            "order_de_referencia": order_de_referencia,
            "Referencia_envio": Referencia_envio,
            "Referencia_recibido": Referencia_recibido,
            "Terminos_de_entrega": Terminos_de_entrega,
            "Tasa_cambio": Tasa_cambio,
            "AdditionalDocumentReference": AdditionalDocumentReference,
            "Anticipos": Anticipos,
            "Productos_servicios": Productos_servicios
        }
        return datafe

    def _set_validation_date(self, invoice, xml_response):
        try:
            xml_issue_date = re.search(
                r'<cbc:IssueDate>(.*)</cbc:IssueDate>',
                xml_response).group(1)
            xml_issue_time = re.search(
                r'<cbc:IssueTime>(.*)</cbc:IssueTime>',
                xml_response).group(1)
            invoice.ei_validation_date = ' '.join(
                (xml_issue_date, xml_issue_time))
        except:
            invoice.ei_validation_date = invoice.ei_generation_date

    def send_to_provider(self, url, datafe, invoice):
        data = 'json_data=' + \
            base64.b64encode(json.dumps(datafe).encode(
                'utf-8')).decode('utf-8')
        try:
            response = requests.post(
                url, data=data, headers=HEADERS, verify=False)
            self.create_transaction_log(
                invoice, 'sent',
                json.dumps(datafe).encode('utf-8'), 'json'
            )
            return response
        except:
            self.create_transaction_log(
                invoice, 'exception', SEND_ERROR
            )
            return {}

    def process_response(self, response, invoice):
        document_type = invoice.journal_id.resolution_id.document_type
        try:
            response_body = response.content.decode('utf-8')
            valid = re.search(r'valid: \'(\w*)\'', response_body).group(1)
            cufe = (re.search(r'cufe: \'(\w*)\'', response_body).group(1)
                    if document_type == '01' else '')
            cude = (re.search(r'cufe: \'(\w*)\'', response_body).group(1)
                    if document_type in ('91', '92') else '')
            qr_code = re.search(r'qr: \'(.*)\'', response_body).group(1)
            response_64 = re.search(
                r'response_64: \'(.*)\'', response_body).group(1)
            response_xml = str(base64.b64decode(response_64), 'utf-8')
            info_check = (invoice.name in response_xml
                          if invoice.company_id.ei_environment == 'production' else True)
            _logger.info("Verificacion de informacion recibida: %s, %s" % (
                invoice.name, info_check))
            if not info_check:
                self.create_transaction_log(
                    invoice, 'provider_error', PROVIDER_ERROR
                )
                invoice.ei_state = 'exception'
                return {}
            if not re.search('Documento validado por la DIAN', response_xml):
                self.create_transaction_log(
                    invoice, 'dian_reject', response_xml
                )
                invoice.ei_state = 'dian_reject'
                return {}
            response_xml = base64.b64decode(response_64)
            self._set_validation_date(invoice, response_xml)
            return {
                'valid': valid,
                'cufe': cufe,
                'cude': cude,
                'qr': qr_code,
                'response_64': response_xml
            }
        except:
            error_log = re.search(
                r'response_error: \'(.*)\'', response_body)
            log_content = (error_log.group(1)
                           if error_log
                           else (response_body or response.content or ''))
            self.create_transaction_log(
                invoice, 'dian_reject', log_content
            )
            invoice.ei_state = 'dian_reject'
            return {}

    def send_invoice(self, invoice):
        company = invoice.company_id
        datafe = self._get_invoice_json(invoice)
        if not datafe:
            return False
        response = self.send_to_provider(company.service_url, datafe, invoice)
        if not response:
            return False
        result = self.process_response(response, invoice)
        if not result:
            return False
        invoice.ei_cufe = result['cufe']
        invoice.ei_cude = result['cude']
        invoice.ei_qr = result['qr']
        response_64 = result['response_64']
        invoice.ei_state = 'dian_accept'
        invoice.create_transaction_log(
            invoice, 'dian_accept', response_64, 'app_response'
        )
        self.env.cr.commit()

    def generate_electronic_invoice(self):
        company = self.mapped(lambda invoice: invoice.company_id)
        if not company.electronic_invoice or company.ei_database != self._cr.dbname:
            raise ValidationError(WRONG_DB_MATCH_WARNING)
        if not company.ei_environment:
            raise ValidationError(ENV_MISSING_WARNING)
        if not company.ei_id_customization:
            raise ValidationError(OP_TYPE_MISSING_WARNING)
        #
        to_send_invoices = self.filtered(
            lambda invoice: invoice.ei_state
            not in ('dian_accept', 'customer_accept', 'customer_reject')
            and invoice.move_type in ['out_invoice', 'out_refund'])
        for invoice in to_send_invoices:
            self.send_invoice(invoice)
            if invoice.ei_state != 'dian_accept':
                continue
            if not company.auto_acceptance_email:
                continue
            invoice.send_acknowlegement_email()

    # Email Management

    def get_invoice_attachments(self):
        self.ensure_one()
        self.get_attachments()
        return True

    def resend_acknowlegement_email(self):
        self.send_acknowlegement_email(force_send=True)

    def valid_email_address(self):
        regex = r'(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)'
        emails = self.partner_id.email or ''
        email_list = emails.split(';')
        return list(filter(
            lambda email: re.match(regex, email),
            map(lambda email: parseaddr(email)[1], email_list)))

    def send_acknowlegement_email(self, force_send=False):
        email_pool = self.env['mail.mail']
        for invoice in self:
            invoice._create_token()
            if not invoice.valid_email_address():
                self.create_transaction_log(
                    invoice, 'email_fail', INVALID_EMAIL_ERROR
                )
                continue
            email = invoice.prepare_email()
            if not email:
                _logger.error(EMAIL_GENERATION_ERROR, invoice.name)
                continue
            email_pool = email_pool + email
            invoice.create_transaction_log(invoice, 'email_sent', 'OK')
            invoice.ei_email_sent = True
        if force_send:
            email_pool.send()

    def prepare_email(self):
        self.ensure_one()
        mail_pool = self.env['mail.mail']
        ctx = self._context.copy()
        ctx.update({
            'dbname': self._cr.dbname,
        })
        template = self.env.ref(
            'electronic_invoice_dian.electronic_invoice_customer_acknowlegement')
        try:
            mail_id = template.with_context(ctx).send_mail(
                self.id, force_send=False)
        except:
            return mail_pool
        mail = mail_pool.browse(mail_id)
        attachment_ids = self.get_attachments()
        if not attachment_ids:
            return mail_pool
        zipped_attachments = self._zip_attachments(attachment_ids)
        if zipped_attachments:
            mail.write({'attachment_ids': [(6, 0, zipped_attachments.ids)]})
            return mail
        return mail_pool

    # Mail attachments

    def _zip_attachments(self, attachments):
        self.ensure_one()
        filestore = os.path.join(
            config['data_dir'], 'filestore', self.env.cr.dbname, )
        xml_file, pdf_file, = self.name + '.xml', self.name + '.pdf'
        zip_file = self.name + '.zip'
        att_zip_file = 'anexos_' + zip_file
        invoice_attachments = attachments.filtered(
            lambda att: att.name in [xml_file, pdf_file])
        other_attachments = attachments.filtered(
            lambda att: att.name not in [xml_file, pdf_file])
        current_dir = os.getcwd()
        try:
            os.chdir(self.company_id.ei_tmp_path)
            if other_attachments:
                with ZipFile(att_zip_file, 'w') as zip_invoice:
                    for att in other_attachments:
                        zip_invoice.write(os.path.join(
                            filestore, att.store_fname), att.name)
            with ZipFile(zip_file, 'w') as zip_invoice:
                for att in invoice_attachments:
                    zip_invoice.write(os.path.join(
                        filestore, att.store_fname), att.name)
                if other_attachments:
                    zip_invoice.write(att_zip_file, att_zip_file)
            zipped_attachment = self.env['ir.attachment'].sudo().create({
                'name': zip_file,
                'type': 'binary',
                'datas': base64.encodebytes(open(zip_file, 'br').read()),
                'res_model': 'account.move',
                'res_id': self.id,
                'mimetype': 'application/zip'
            })
            map(os.remove, [zip_file] +
                ([att_zip_file] if other_attachments else[]))
            os.chdir(current_dir)
            return zipped_attachment
        except Exception as exc:
            _logger.error(exc)
            os.chdir(current_dir)
            return attachments

    def get_attachments(self):
        company = self.company_id
        xml_file = self.name + '.xml'
        pdf_file = self.name + '.pdf'
        attachment_pool = self.env['ir.attachment']
        attachment_domain = [
            ('res_model', '=', 'account.move'),
            ('res_id', '=', self.id),
        ]
        attachment_ids = attachment_pool.search(attachment_domain)
        attachment_names = attachment_ids.mapped(lambda att: att.name)
        if xml_file not in attachment_names:
            if not self.create_xml_attachment():
                return attachment_pool
        if pdf_file not in attachment_names:
            if not self.create_pdf_attachment():
                return attachment_pool
        updated_attachment_ids = attachment_pool.search(
            attachment_domain)
        sale_order_attachments = (company.attach_customer_order
                                  and self.get_sale_order_attachments()
                                  or attachment_pool)
        picking_attachments = (company.attach_delivery_note
                               and self.get_picking_attachments()
                               or attachment_pool)
        if company.attach_invoice_docs:
            return (updated_attachment_ids + sale_order_attachments
                    + picking_attachments)
        xml_and_pdf_attachments = updated_attachment_ids.filtered(
            lambda att: att.name in (xml_file, pdf_file)
        )
        return (xml_and_pdf_attachments + sale_order_attachments
                + picking_attachments)

    def _get_xml_json(self, invoice):
        company = self.company_id
        company_partner = company.partner_id
        document_type = invoice.journal_id.resolution_id.document_type
        return {
            "datos_conexion": {
                "token": company.software_token,
                "documento": company_partner.ref_num
            },
            "key": {
                "cufe": invoice.ei_cufe if document_type == '01' else invoice.ei_cude
            },
            "Datos_software": {
                "ambiente": ("1" if company.ei_environment == 'production'
                             else "0")
            }
        }

    def get_xml(self, datafe):
        data = 'json_data=' + \
            base64.b64encode(json.dumps(datafe).encode(
                'utf-8')).decode('utf-8')
        try:
            response = requests.post(
                URL_XML, data=data, headers=HEADERS, verify=False)
            xmlb64 = re.search(
                r'<b:XmlBytesBase64>(.*)</b:XmlBytesBase64>',
                str(response.content, 'utf-8')).group(1)
            xml_fe = base64.b64decode(xmlb64)
            return xml_fe
        except:
            pass
        return ''

    def create_xml_attachment(self):
        xml_fe = self.ei_xml_content or self.get_xml(self._get_xml_json(self))
        if not xml_fe:
            return False
        if not self.ei_xml_content:
            self.ei_xml_content = xml_fe
        filename = self.name + '.xml'
        xml_att_document = self.build_attached_document()
        xml_fe_normalized = (xml_att_document.encode('utf-8') if
                             isinstance(xml_att_document, str) else xml_att_document)
        data_attach = {
            'name': filename,
            'datas': base64.b64encode(xml_fe_normalized),
            'res_model': 'account.move',
            'res_id': self.id,
            'mimetype': 'application/xml',
            'type': 'binary'
        }
        return self.env['ir.attachment'].sudo().create(data_attach)

    def create_pdf_attachment(self):
        self.ensure_one()
        report = self.company_id.ei_report_id
        if report and report.report_type == 'qweb-pdf':
            try:
                report._render_qweb_pdf(self.id)
                return True
            except Exception:
                raise ValidationError(PDF_GENERATION_ERROR)
        else:
            raise ValidationError(UNSUPPORTED_PDF_FORMAT_WARNING)

    def get_order_attachment(self, order):
        attachment_pool = self.env['ir.attachment']
        if not order.customer_po_file:
            return attachment_pool
        filename = order.customer_po_name or 'OrdenDeCompra.pdf'
        existing_attachment = attachment_pool.search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
            ('name', '=', filename),
        ])
        if existing_attachment:
            return existing_attachment
        data_attach = {
            'name': filename,
            'datas': order.customer_po_file,
            'res_model': 'sale.order',
            'res_id': order.id,
            'mimetype': 'application/pdf',
            'type': 'binary'
        }
        return self.env['ir.attachment'].sudo().create(data_attach)

    def get_sale_orders(self):
        order_lines = self.env['sale.order.line'].search([
            ('invoice_lines', 'in', self.invoice_line_ids.ids)
        ])
        orders = order_lines.mapped(lambda line: line.order_id)
        return orders

    def get_sale_order_attachments(self):
        self.ensure_one()
        attachment_pool = self.env['ir.attachment']
        orders = self.get_sale_orders()
        if not orders:
            return attachment_pool
        attachments = orders.mapped(self.get_order_attachment)
        return attachments

    def get_picking_attachments(self):
        return self.env['ir.attachment']

    # Mass send, Unused

    def ei_email_mass_send(self):
        to_email_invoices = self.env['account.move'].search([
            ('ei_state', '=', 'dian_accep'),
            ('ei_email_sent', '=', False)
        ], limit=100)
        to_email_invoices.send_acknowlegement_email()

    # XML AttachedDocument

    def _get_header_tags(self):
        company = self.company_id
        utc_adj = '-05:00'
        return {
            'UBLVersionID': 'DIAN 2.1',
            'CustomizationID': 'Documentos adjuntos',
            'ProfileID': 'DIAN 2.1',
            'ProfileExecutionID': ("1" if company.ei_environment == 'production' else "2"),
            'ID': uuid.uuid4().hex,
            'IssueDate': self.ei_generation_date.split(' ')[0],
            'IssueTime': self.ei_generation_date.split(' ')[1],
            'DocumentType': u'Contenedor de Factura Electrónica',
            'ParentDocumentID': str(self.name)
        }

    def _get_sender_tags(self):
        company = self.company_id
        return {
            'RegistrationName': company.name,
            'CompanyID': company.partner_id.ref_num,
            'TaxLevelCode': company.tributary_obligations or 'R-99-PN',
            'ID': '01',
            'Name': 'IVA'
        }

    def _get_sender_attrs(self):
        company = self.company_id
        return {
            'CompanyID': {
                'schemeAgencyID': "195",
                'schemeID': ("1" if company.ei_environment == 'production' else "2"),
                'schemeName': company.partner_id.ref_type_id.code_dian
            },
            'TaxLevelCode': {
                'listName': "48"
            },
        }

    def _get_receiver_tags(self):
        return {
            'RegistrationName': self.partner_id.name,
            'CompanyID': self.partner_id.ref_num,
            'TaxLevelCode': 'R-99-PN',
            'ID': '01',
            'Name': 'IVA'
        }

    def _get_receiver_attrs(self):
        company = self.company_id
        return {
            'CompanyID': {
                'schemeAgencyID': "195",
                'schemeID': ("1" if company.ei_environment == 'production' else "2"),
                'schemeName': self.partner_id.ref_type_id.code_dian
            },
            'TaxLevelCode': {
                'listName': "48"
            },
        }

    def _get_attachment_tags(self):
        return {
            'MimeCode': 'text/xml',
            'EncodingCode': 'UTF-8',
            'Description': 'ei_xml_content',
        }

    def _get_doc_line_tags(self):
        issue_date = self.ei_generation_date
        validation_date, validation_time = (self.ei_validation_date.split(
            ' ') if self.ei_validation_date else ('', ''))
        return {
            'LineID': '1',
            'ID': self.name,
            'UUID': (self.ei_cufe or self.ei_cude),
            'IssueDate': issue_date[:10],
            'DocumentType': 'ApplicationResponse',
            'MimeCode': 'text/xml',
            'EncodingCode': 'UTF-8',
            'Description': 'ei_app_response',
            'ValidatorID': u'Unidad Especial Dirección de Impuestos y Aduanas Nacionales',
            'ValidationResultCode': u'02',
            'ValidationDate': str(validation_date),
            'ValidationTime': str(validation_time),
        }

    def _get_doc_line_attrs(self):
        return {
            'UUID': {
                'schemeName': "CUFE-SHA384"
            }
        }

    def build_attached_document(self):
        vals = {
            'header': {
                'tags': self._get_header_tags(),
                'attrs': {}
            },
            'sender': {
                'tags': self._get_sender_tags(),
                'attrs': self._get_sender_attrs()
            },
            'receiver': {
                'tags': self._get_receiver_tags(),
                'attrs': self._get_receiver_attrs()
            },
            'attachment': {
                'tags': self._get_attachment_tags(),
                'attrs': {}
            },
            'doc_line': {
                'tags': self._get_doc_line_tags(),
                'attrs': self._get_doc_line_attrs()
            }
        }
        log_app_response = self.transaction_log_ids.filtered(
            lambda log: log.document_type == 'app_response')
        app_response = log_app_response[0].content if log_app_response else ''
        return xml_helper.build_xml_attached_document(
            self.ei_xml_content, app_response, vals)

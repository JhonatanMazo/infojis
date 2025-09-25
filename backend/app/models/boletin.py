from app import db
from datetime import datetime
import json

class Boletin(db.Model):
    __tablename__ = 'boletines'

    id = db.Column(db.Integer, primary_key=True)
    id_matricula = db.Column(db.Integer, db.ForeignKey('matricula.id'), nullable=False)
    id_periodo = db.Column(db.Integer, db.ForeignKey('periodos.id', ondelete='CASCADE'), nullable=False)
    id_curso = db.Column(db.Integer, db.ForeignKey('cursos.id', ondelete='CASCADE'), nullable=False)
    # grades_data will store a JSON string or similar structure for grades per subject
    grades_data = db.Column(db.Text, nullable=True)
    anio_lectivo = db.Column(db.String(9), nullable=False)
    comments = db.Column(db.Text, nullable=True)
    generated_date = db.Column(db.DateTime, default=datetime.utcnow)
    generated_by_user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)

    # Soft delete columns
    eliminado = db.Column(db.Boolean, default=False)
    eliminado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    fecha_eliminacion = db.Column(db.DateTime, nullable=True)

    # Relationships - CORREGIDAS
    matricula = db.relationship('Matricula', back_populates='boletines')
    periodo = db.relationship('Periodo', backref='boletines', lazy=True)
    curso = db.relationship('Curso', back_populates='boletines')
    generated_by = db.relationship('User', backref='boletines_generados', lazy=True, foreign_keys=[generated_by_user_id])
    eliminado_por_user = db.relationship('User', backref='boletines_eliminados', lazy=True, foreign_keys=[eliminado_por])  # ¡CORREGIDO!

    @property
    def estudiante_nombre(self):
        return f"{self.matricula.nombres} {self.matricula.apellidos}"

    @property
    def curso_nombre(self):
        return self.curso.nombre

    @property
    def periodo_nombre(self):
        return self.periodo.nombre

    @property
    def promedio(self):
        if not self.grades_data:
            return 0.0
        
        try:
            grades = json.loads(self.grades_data)
        except json.JSONDecodeError:
            return 0.0

        if not isinstance(grades, dict):
            return 0.0

        notas_validas = []
        for data in grades.values():
            nota = data.get('nota')
            if nota is not None and nota != '':
                try:
                    notas_validas.append(float(nota))
                except (ValueError, TypeError):
                    continue
        
        if not notas_validas:
            return 0.0
            
        return sum(notas_validas) / len(notas_validas)

    @property
    def fecha_creacion(self):
        return self.generated_date

    @property
    def creado_por(self):
        return f"{self.generated_by.nombre} {self.generated_by.apellidos}"

    def __repr__(self):
        return f'<Boletin {self.id} for Matricula {self.id_matricula} Period {self.id_periodo}>'
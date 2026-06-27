"""Модели данных базы данных"""

from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base


class Module(Base):
    """Таблица module"""
    __tablename__ = 'module'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    round_to = Column(Integer, nullable=False)
    dynamic_diversities_intervals = Column(String(1024))
    const_diversities_count = Column(Integer, nullable=False)
    dynamic_diversities_count = Column(Integer)
    min_out_val = Column(Float, nullable=False)
    max_out_val = Column(Float)

    experiment_data_items = relationship("ExperimentData", back_populates="module_obj")

    def __repr__(self):
        return f"<Module(id={self.id}, name='{self.name}')>"


class Version(Base):
    """Таблица version"""
    __tablename__ = 'version'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    const_diversities_coordinates = Column(String(512))
    dynamic_diversities_coordinates = Column(String(512))
    reliability = Column(Float, nullable=False)
    module = Column(Integer, ForeignKey('module.id'))

    experiment_data_items = relationship("ExperimentData", back_populates="version_obj")

    def __repr__(self):
        return f"<Version(id={self.id}, name='{self.name}')>"


class Algorithm(Base):
    """Таблица algorithm"""
    __tablename__ = 'algorithm'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(127), nullable=False)
    src_code = Column(Text)
    module_name = Column(String(255), nullable=False)
    func_name = Column(String(127), nullable=False)
    module_pkg = Column(String(255))

    vote_results = relationship("VoteResult", back_populates="algorithm_obj")

    def __repr__(self):
        return f"<Algorithm(id={self.id}, name='{self.name}')>"


class ExperimentData(Base):
    """Таблица experiment_data - основная таблица данных"""
    __tablename__ = 'experiment_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    version_id = Column(Integer, ForeignKey('version.id'), nullable=False)
    version_name = Column(String(255))
    version_reliability = Column(Float, nullable=False)
    version_common_coordinates = Column(String(1024), nullable=False)
    version_answer = Column(Float, nullable=False)
    correct_answer = Column(Float, nullable=False)
    module_id = Column(Integer, ForeignKey('module.id'), nullable=False)
    module_name = Column(String(255))
    module_connectivity_matrix = Column(String(4095))
    module_iteration_num = Column(Integer, nullable=False)
    experiment_name = Column(String(31), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            'version_id', 'version_reliability', 'version_common_coordinates',
            'version_answer', 'correct_answer', 'module_id',
            'module_connectivity_matrix', 'module_iteration_num',
            name='uq_experiment_data'
        ),
    )

    version_obj = relationship("Version", back_populates="experiment_data_items")
    module_obj = relationship("Module", back_populates="experiment_data_items")
    vote_results = relationship("VoteResult", back_populates="experiment_data_obj")

    def __repr__(self):
        return f"<ExperimentData(id={self.id}, exp='{self.experiment_name}', v={self.version_name})>"


class VoteResult(Base):
    """Таблица vote_result - результаты голосования"""
    __tablename__ = 'vote_result'

    id = Column(Integer, primary_key=True, autoincrement=True)
    algorithm_id = Column(Integer, ForeignKey('algorithm.id'), nullable=False)
    experiment_data_id = Column(Integer, ForeignKey('experiment_data.id'), nullable=False)
    vote_answer = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            'algorithm_id', 'experiment_data_id', 'vote_answer',
            name='uq_vote_result'
        ),
    )

    algorithm_obj = relationship("Algorithm", back_populates="vote_results")
    experiment_data_obj = relationship("ExperimentData", back_populates="vote_results")

    def __repr__(self):
        return f"<VoteResult(id={self.id}, answer={self.vote_answer})>"


class VotingRun(Base):
    """Новая таблица для сохранения запусков голосования"""
    __tablename__ = 'voting_run'

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_name = Column(String(31), nullable=False)
    algorithm_type = Column(String(50), nullable=False)  # 'median', 'majority', etc.
    median_type = Column(String(50))  # 'median', 'median_low', 'median_high', 'weighted'
    epsilon = Column(Float, nullable=False)
    module_id = Column(Integer, nullable=False)
    module_name = Column(String(255))
    voted_value = Column(Float)
    correct_answer = Column(Float)
    is_correct = Column(Integer)  # 0 или 1
    deviation = Column(Float)
    versions_count = Column(Integer, nullable=False)
    versions_answers = Column(Text)  # JSON список ответов
    total_records = Column(Integer)
    total_modules = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<VotingRun(id={self.id}, exp='{self.experiment_name}', algo='{self.algorithm_type}')>"
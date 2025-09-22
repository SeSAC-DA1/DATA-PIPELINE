from sqlalchemy import Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Vehicle(Base):
    __tablename__ = 'vehicles'
    
    vehicleid = Column(Integer, primary_key=True, autoincrement=True)
    carseq = Column(Integer, nullable=False)
    vehicleno = Column(String, nullable=False, unique=True)
    platform = Column(String)
    origin = Column(String)
    cartype = Column(String)
    manufacturer = Column(String)
    model = Column(String)
    generation = Column(String)
    trim = Column(String)
    fueltype = Column(String)
    transmission = Column(String)
    colorname = Column(String)
    modelyear = Column(Integer)
    firstregistrationdate = Column(Integer)
    distance = Column(Integer)
    price = Column(Integer)
    originprice = Column(Integer)
    selltype = Column(String)
    location = Column(String) 
    detailurl = Column(String)
    photo = Column(String)


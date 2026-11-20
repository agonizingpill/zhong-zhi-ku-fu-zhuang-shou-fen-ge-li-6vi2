from datetime import date
from pydantic import BaseModel,Field,model_validator
class Login(BaseModel):
    email:str
    password:str
class AccessionInput(BaseModel):
    code:str=Field(min_length=3,max_length=40,pattern=r'\S')
    crop:str=Field(min_length=2,max_length=40)
    name:str=Field(min_length=2,max_length=100)
    origin:str=Field(min_length=2,max_length=100)
    minimum:int=Field(ge=100,le=10000)
class LotInput(BaseModel):
    accession_id:int
    code:str=Field(min_length=3,max_length=60)
    generation:int=Field(ge=0,le=30)
    available:int=Field(ge=1,le=1000000)
    stored_months:float=Field(ge=0,le=120,allow_inf_nan=False)
    temperature:float=Field(ge=-25,le=35,allow_inf_nan=False)
    initial_rate:float=Field(ge=0,le=100,allow_inf_nan=False)
class TestInput(BaseModel):
    lot_id:int
    code:str=Field(min_length=3,max_length=60)
    sampled:int=Field(ge=20,le=1000)
    germinated:int=Field(ge=0)
    @model_validator(mode='after')
    def valid(self):
        if self.germinated>self.sampled:raise ValueError('发芽粒数不能超过抽样粒数')
        return self
class RegenerationInput(BaseModel):
    test_id:int
    code:str=Field(min_length=3,max_length=60)
    issued:int=Field(ge=10,le=10000)
    reason:str=Field(min_length=4,max_length=300)
class FlowerInput(BaseModel):
    regeneration_id:int
    plot_id:int
    start:date
    end:date
    @model_validator(mode='after')
    def valid(self):
        if self.end<self.start:raise ValueError('花期结束不得早于开始')
        if (self.end-self.start).days>60:raise ValueError('花期不超过60天')
        return self
class PollenInput(BaseModel):
    regeneration_id:int
    mother_lot_id:int
    father_lot_id:int
    bag_code:str=Field(min_length=3,max_length=60)
    bagged:bool
    flowers:int=Field(ge=1,le=10000)
class HarvestInput(BaseModel):
    regeneration_id:int
    code:str=Field(min_length=3,max_length=60)
    seeds:int=Field(ge=1,le=1000000)
    moisture:float=Field(ge=0,le=40,allow_inf_nan=False)
class DistributionInput(BaseModel):
    lot_id:int
    code:str=Field(min_length=3,max_length=60)
    recipient:str=Field(min_length=2,max_length=100)
    seeds:int=Field(ge=1,le=10000)
    purpose:str=Field(min_length=5,max_length=300)
class ApproveInput(BaseModel):
    leave_date:date|None=None
class ReturnBagInput(BaseModel):
    bag_no:str=Field(min_length=1,max_length=40,pattern=r'\S')
    seeds:int=Field(ge=1,le=10000)
    sampled:int|None=Field(default=None,ge=1,le=10000)
    germinated:int|None=Field(default=None,ge=0)
    @model_validator(mode='after')
    def valid(self):
        if self.sampled is not None and self.germinated is not None and self.germinated>self.sampled:raise ValueError('发芽粒数不能超过抽样粒数')
        if (self.sampled is None)!=(self.germinated is None):raise ValueError('抽样粒数与发芽粒数须同时填写')
        if self.sampled is not None and self.sampled>self.seeds:raise ValueError('抽样粒数不能超过本袋粒数')
        return self
class ReturnInput(BaseModel):
    distribution_id:int
    code:str=Field(min_length=3,max_length=60)
    return_date:date|None=None
    bags:list[ReturnBagInput]=Field(min_length=1,max_length=50)
    @model_validator(mode='after')
    def valid(self):
        nos=[b.bag_no for b in self.bags]
        if len(nos)!=len(set(nos)):raise ValueError('同一退种单内袋号不可重复')
        return self
class RetestInput(BaseModel):
    sampled:int=Field(ge=20,le=1000)
    germinated:int=Field(ge=0)
    @model_validator(mode='after')
    def valid(self):
        if self.germinated>self.sampled:raise ValueError('发芽粒数不能超过抽样粒数')
        return self
class AcceptInput(BaseModel):
    sampled:int|None=Field(default=None,ge=1,le=10000)
    germinated:int|None=Field(default=None,ge=0)
    @model_validator(mode='after')
    def valid(self):
        if self.sampled is not None and self.germinated is not None and self.germinated>self.sampled:raise ValueError('发芽粒数不能超过抽样粒数')
        if (self.sampled is None)!=(self.germinated is None):raise ValueError('抽样粒数与发芽粒数须同时填写')
        return self

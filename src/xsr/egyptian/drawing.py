"""Vector enclosure and damage drawing, independent of font glyph recipes."""
import math


def decoration_tex(dec):
    def n(v):
        return f'{v:.6f}'.rstrip('0').rstrip('.') or '0'
    def point(x,y):
        return r'\xsrEgyptianPoint'+'{'+n(x)+'}{'+n(y)+'}'
    def move(x,y):
        return r'\pgfpathmoveto{'+point(x,y)+'}'
    def line(x,y):
        return r'\pgfpathlineto{'+point(x,y)+'}'
    def curve(x1,y1,x2,y2,x3,y3):
        return r'\pgfpathcurveto{'+point(x1,y1)+'}{'+point(x2,y2)+'}{'+point(x3,y3)+'}'
    w,h=dec.width,dec.height
    t=dec.stroke/2
    if dec.kind=='shade':
        body=r'\pgfpathrectangle{\pgfpointorigin}{'+point(w,h)+r'}\pgfusepath{clip}\pgfsetstrokecolor{gray}'
        step=.075
        for i in range(-math.ceil(h/step),math.ceil(w/step)+1):
            x=i*step - ((dec.x+dec.y+dec.height+dec.phase) % step)
            body+=move(x,0)+line(x+h,h)
    elif dec.kind.startswith('bracket-'):
        cp=int(dec.kind.split('-')[1])
        closing=cp in (0x5D,0x7D,0x27E9,0x27E7,0x2E23)
        x0,x1=(w-t,t) if closing else (t,w-t)
        if cp in (0x27E8,0x27E9):
            body=move(x1,t)+line(x0,h/2)+line(x1,h-t)
        elif cp in (0x7B,0x7D):
            mid=(x0+x1)/2
            body=move(x1,t)+curve(x0,t,x1,h*.4,x0,h/2)+curve(x1,h*.6,x0,h-t,x1,h-t)
        else:
            bottom=h/2 if cp in (0x2E22,0x2E23) else t
            body=move(x1,h-t)+line(x0,h-t)+line(x0,bottom)
            if bottom==t:
                body+=line(x1,t)
            if cp in (0x27E6,0x27E7):
                body+=move((x0+x1)/2,t)+line((x0+x1)/2,h-t)
    elif dec.kind=='cartouche':
        r=(h-2*t)/2
        left,right=t+r,w-t-r
        body=move(left,t)+line(right,t)+move(left,h-t)+line(right,h-t)
        k=.5522847498
        if dec.ends[0]:
            body+=move(left,t)+curve(left-k*r,t,t,r+t-k*r,t,r+t)+curve(t,r+t+k*r,left-k*r,h-t,left,h-t)
        if dec.ends[1]:
            x=right+r
            body+=move(right,t)+curve(right+k*r,t,x,r+t-k*r,x,r+t)+curve(x,r+t+k*r,right+k*r,h-t,right,h-t)
            body+=move(w-t,t)+line(w-t,h-t)
    elif dec.kind in ('rectangle','walled'):
        if dec.kind=='rectangle':
            body=move(t,t)+line(w-t,t)+move(t,h-t)+line(w-t,h-t)
        else:
            body=''
            count=max(2,math.ceil(w/.14))
            for base,sign in ((t,1),(h-t,-1)):
                body+=move(t,base)
                for i in range(count):
                    x1=t+(w-2*t)*(i+.25)/count
                    x2=t+(w-2*t)*(i+.75)/count
                    body+=line(x1,base)+line(x1,base+sign*.04)+line(x2,base+sign*.04)+line(x2,base)
                body+=line(w-t,base)
        if dec.ends[0]:
            body+=move(t,t)+line(t,h-t)
        if dec.ends[1]:
            body+=move(w-t,t)+line(w-t,h-t)
    else:
        raise ValueError(f'unknown decoration {dec.kind}')
    body+=r'\pgfusepath{stroke}'
    if dec.mirror:
        body=r'\pgftransformshift{'+point(w,0)+r'}\pgftransformxscale{-1}'+body
    return r'\xsrEgyptianDecoration'+''.join('{'+n(v)+'}' for v in (dec.x,dec.y,dec.height,dec.stroke))+'{'+body+'}'

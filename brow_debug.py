import math,pygame
pygame.init()
s=pygame.display.set_mode((1280,720))
f=pygame.font.SysFont(None,22)
c=pygame.time.Clock()
rx,ry,sp=135,168,320
cx,cy=640,380
bw,bh=rx,ry
ww,wh=int(bw*1.9),int(bh*1.3)
g=2
yo=-35
R=True
while R:
    for e in pygame.event.get():
        if e.type==pygame.QUIT:R=False
        elif e.type==pygame.KEYDOWN and e.key in(pygame.K_ESCAPE,pygame.K_q):R=False
    s.fill((240,208,192))
    for sd in [-1,1]:
        ex,ey=cx+sd*sp,cy
        pygame.draw.ellipse(s,(250,250,250),(ex-ww,ey-wh,ww*2,wh*2))
        for i in range(24):
            a=2*math.pi*i/24
            px,py=ex+int(ww*math.cos(a)),ey-int(wh*math.sin(a))
            pygame.draw.circle(s,(0,0,0),(px,py),4)
            s.blit(f.render(str(i),True,(255,0,0)),(px+6,py-8))
        # 圆点眉毛: 左眼3->7, 右眼5->9
        if sd<0:aa,ab=45.0,105.0
        else:aa,ab=75.0,135.0
        br=48
        n=20
        for i in range(n):
            t=i/(n-1)
            a=math.radians(aa+(ab-aa)*t)
            px=ex+int((ww+g)*math.cos(a))
            py=ey-int((wh+g)*math.sin(a))+yo
            ef=0.7+0.3*math.sin(t*math.pi)
            r=max(1,int(br*ef))
            pygame.draw.circle(s,(38,26,22),(px,py-r-35),r)
            # 标号
            s.blit(f.render(str(i),True,(0,200,0)),(px+r+2,py-r-35-8))
    s.blit(f.render('Red=eye dots, Green=brow dot index',True,(100,100,100)),(10,10))
    pygame.display.flip()
    c.tick(30)
pygame.quit()

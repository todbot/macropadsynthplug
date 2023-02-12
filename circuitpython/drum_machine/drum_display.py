#
#
#
# Screen looks like:
#
# +----------+  +----------+
# |macropad  |  |macropad  |
# |synthplug |  |synthplug |
# |drumachine|  |drumachine|
# |     play |  |          |
# |>patt     |  |>save pats|
# | patt1a   |  |          |
# |>kit      |  |>del pat  |
# | tr808    |  |          |
# |>bpm: 120 |  |>midi:rcv |  # 'rcv' or 'off'
# |          |  |          |
# |hold2save |  |>aud:plug |  # 'plug' or 'spk'  maybe
# +----------+  +----------+
#

import board
import displayio, terminalio
from adafruit_display_text.bitmap_label import Label

# display setup begin
dw,dh = 64,128
display = board.DISPLAY
display.rotation = 90
font = terminalio.FONT

mainscreen = displayio.Group()
display.root_group = mainscreen

txt1 = Label(font, text="macropad",       x=0, y=10)
txt2 = Label(font, text="synthplug",      x=0, y=20)
txt3 = Label(font, text="drumachine",     x=0, y=30)
txt_emode0  = Label(font,text=">",        x=0, y=55)
txt_emode1  = Label(font,text=" ",        x=0, y=70)
txt_emode2  = Label(font,text=" ",        x=0, y=85)

txt_play    = Label(font, text="stop" ,  x=40, y=45)
txt_patt    = Label(font, text="patt",    x=6, y=55)
txt_kit     = Label(font, text="kit:",    x=6, y=70)
txt_bpm     = Label(font, text="bpm:",    x=6, y=85)
txt_bpm_val = Label(font, text='120',    x=35, y=85)

txt_midi    = Label(font, text="midi:",   x=0, y=110)
txt_info    = Label(font, text="   ",     x=0, y=120)

for t in (txt1, txt2, txt3, txt_emode0, txt_emode1, txt_emode2,
          txt_play, txt_patt, txt_kit, txt_bpm, txt_bpm_val,
          txt_midi, txt_info):
    mainscreen.append(t)


# display setup end

#
# Display updates
#

# update step_millis and display
def disp_bpm(bpm):
    txt_bpm_val.text = str(bpm)

# update display
def disp_play(playing,recording):
    if playing:
        txt_play.text = "play" if not recording else "odub"
    else:
        txt_play.text = "stop" if not recording else "reco"  # FIXME:

# update display
def disp_pattern(name):
    txt_patt.text = name

def disp_kit(name):
    txt_kit.text = name

# update display
def disp_encmode(encoder_mode):
    txt_emode0.text = '>' if encoder_mode==0 else ' '
    txt_emode1.text = '>' if encoder_mode==1 else ' '
    txt_emode2.text = '>' if encoder_mode==2 else ' '

def disp_info(astr):
    txt_info.text = astr

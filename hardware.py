#!/usr/bin/python
import sys
from machinekit import hal
from machinekit import rtapi as rt
from machinekit import config as c
if sys.version_info >= (3, 0):
    import configparser
else:
    import ConfigParser as configparser


class Motor():
    def __init__(self, name='motor', thread='base_thread', eqep='eQEP0',
                 eqepScale=2797.0, pgain=1.0, igain=0.0, dgain=0.01,
                 pwmDown='hpg.pwmgen.00.out.00',
                 pwmUp='hpg.pwmgen.00.out.01',
                 enableDown='bb_gpio.p9.out-15',
                 enableUp='bb_gpio.p9.out-17'):
        # 43.7:1 gear
        # encoder resolution of 64 counts per revolution of the motor shaft,
        # 2797 counts per revolution of the gearboxs output shaft.

        # for eQEP0.position in shaft revs:
        hal.Pin('%s.position-scale' % eqep).set(eqepScale)
        # feed into PID
        hal.net('%s-pos' % name, '%s.position' % eqep)
        # for UI feedback
        hal.net('%s-vel' % name, '%s.velocity' % eqep)

        sigPgain = hal.newsig('%s-pgain' % name, hal.HAL_FLOAT)
        sigIgain = hal.newsig('%s-igain' % name, hal.HAL_FLOAT)
        sigDgain = hal.newsig('%s-dgain' % name, hal.HAL_FLOAT)
        sigCmdVel = hal.newsig('%s-cmd-vel' % name, hal.HAL_FLOAT)
        sigOutVel = hal.newsig('%s-out-vel' % name, hal.HAL_FLOAT)
        sigVel = hal.newsig('%s-vel' % name, hal.HAL_FLOAT)
        sigAcc = hal.newsig('%s-acc' % name, hal.HAL_FLOAT)
        sigUp = hal.newsig('%s-up' % name, hal.HAL_FLOAT)
        sigDown = hal.newsig('%s-down' % name, hal.HAL_FLOAT)
        sigEnable = hal.newsig('%s-enable' % name, hal.HAL_BIT)
        sigPwmEn = hal.newsig('%s-pwm-enable' % name, hal.HAL_BIT)

        # ddt for accel
        ddt = rt.newinst('i_ddt', 'ddt.%s-acc' % name)
        hal.addf(ddt.name, thread)
        ddt.pin('in').link(sigVel)
        ddt.pin('out').link(sigAcc)

        # PID
        pid = rt.newinst('pid', 'pid.%s-vel' % name)
        hal.addf('%s.do-pid-calcs' % pid.name, thread)
        pid.pin('maxoutput').set(1.0)  # set maxout to prevent windup effect
        pid.pin('Pgain').link(sigPgain)
        pid.pin('Igain').link(sigIgain)
        pid.pin('Dgain').link(sigDgain)
        pid.pin('command').link(sigCmdVel)
        pid.pin('output').link(sigOutVel)
        pid.pin('feedback').link(sigVel)
        pid.pin('enable').link(sigEnable)

        # hbridge
        hbridge = rt.newinst('i_hbridge', 'hbridge.%s' % name)
        hal.addf(hbridge, thread)
        hbridge.pin('up').link(sigUp)
        hbridge.pin('down').link(sigDown)
        hbridge.pin('enable').link(sigEnable)
        hbridge.pin('enable-out').link(sigPwmEn)

        # PWM signals
        hal.Pin('%s.value' % pwmUp).link(sigUp)
        hal.Pin('%s.value' % pwmDown).link(sigDown)

        # Enable
        hal.Pin(enableUp).link(sigPwmEn)
        hal.Pin(enableDown).link(sigPwmEn)
        hal.Pin('%s.enable' % pwmUp).link(sigPwmEn)
        hal.Pin('%s.enable' % pwmDown).link(sigPwmEn)

        sigPgain.set(pgain)
        sigIgain.set(igain)
        sigDgain.set(dgain)

        # prevent pid runup if disabled
        sigEnable.set(True)


def setupPosPid(name='pos', pgain=0.001, igain=0.0, dgain=0.0,
                thread='base_thread'):
    sigPgain = hal.newsig('%s-pgain' % name, hal.HAL_FLOAT)
    sigIgain = hal.newsig('%s-igain' % name, hal.HAL_FLOAT)
    sigDgain = hal.newsig('%s-dgain' % name, hal.HAL_FLOAT)
    sigVel = hal.newsig('%s-vel' % name, hal.HAL_FLOAT)
    sigFeedback = hal.newsig('%s-feedback' % name, hal.HAL_FLOAT)
    sigOutput = hal.newsig('%s-output' % name)
    sigCmd = hal.newsig('%s-cmd' % name)
    sigEnable = hal.newsig('%s-enable' % name)

    pid = rt.newinst('pid', 'pid.%s' % name)
    hal.addf('%s.do-pid-calcs' % pid.name, thread)
    pid.pin('maxoutput').set(1.0)  # set maxout to prevent windup effect
    pid.pin('Pgain').link(sigPgain)
    pid.pin('Igain').link(sigIgain)
    pid.pin('Dgain').link(sigDgain)
    pid.pin('feedback-deriv').link(sigVel)
    pid.pin('feedback').link(sigFeedback)
    pid.pin('output').link(sigOutput)
    pid.pin('command').link(sigCmd)
    pid.pin('enable').link(sigEnable)

    kalman = hal.instances['kalman']
    kalman.pin('rate').link(sigVel)
    kalman.pin('angle').link(sigFeedback)

    # TODO use output
    # TODO use cmd

    sigPgain.set(pgain)
    sigIgain.set(igain)
    sigDgain.set(dgain)

    sigEnable.set(True)


def setupGyro(thread='base_thread'):
    name = 'balance'
    sigReq = hal.newsig('%s-req' % name, hal.HAL_BIT)
    sigAck = hal.newsig('%s-ack' % name, hal.HAL_BIT)
    sigDt = hal.newsig('%s-dt' % name, hal.HAL_FLOAT)
    sigNewAngle = hal.newsig('%s-new-angle' % name, hal.HAL_FLOAT)
    sigNewRate = hal.newsig('%s-new-rate' % name, hal.HAL_FLOAT)

    gyroaccel = hal.loadusr('./hal_gyroaccel', name='gyroaccel',
                            bus_id=1, interval=0.05,
                            wait_name='gyroaccel')
    gyroaccel.pin('req').link(sigReq)
    gyroaccel.pin('ack').link(sigAck)
    gyroaccel.pin('dt').link(sigDt)
    gyroaccel.pin('angle').link(sigNewAngle)
    gyroaccel.pin('rate').link(sigNewRate)
    gyroaccel.pin('invert').set(True)  # invert the output since we mounted the gyro upside down

    kalman = rt.newinst('kalman', 'kalman.%s' % name)
    hal.addf(kalman.name, thread)
    kalman.pin('req').link(sigReq)
    kalman.pin('ack').link(sigAck)
    kalman.pin('dt').link(sigDt)
    kalman.pin('new-angle').link(sigNewAngle)
    kalman.pin('new-rate').link(sigNewRate)


rt.init_RTAPI()
c.load_ini('hardware.ini')

rt.loadrt('hal_bb_gpio', output_pins='915,917,838,840')
rt.loadrt('hal_arm335xQEP', encoders='eQEP0,eQEP2')
rt.loadrt(c.find('PRUCONF', 'DRIVER'), 'prucode=' + c.find('PRUCONF', 'PRUBIN'), pru=0, num_pwmgens=7, halname='hpg')

# pru pwmgens
hal.Pin('hpg.pwmgen.00.pwm_period').set(500000)
# motor left
hal.Pin('hpg.pwmgen.00.out.00.pin').set(911)
hal.Pin('hpg.pwmgen.00.out.01.pin').set(913)
# motor right
hal.Pin('hpg.pwmgen.00.out.02.pin').set(808)
hal.Pin('hpg.pwmgen.00.out.03.pin').set(810)

baseThread = 'base_thread'
rt.newthread(baseThread, 1000000, fp=True)
hal.addf('bb_gpio.read', baseThread)
hal.addf('eqep.update', baseThread)

ml = Motor(name='ml', eqep='eQEP0', eqepScale=2797.0,
           pwmDown='hpg.pwmgen.00.out.00',
           pwmUp='hpg.pwmgen.00.out.01',
           enableDown='bb_gpio.p9.out-15',
           enableUp='bb_gpio.p9.out-17')
mr = Motor(name='mr', eqep='eQEP2', eqepScale=-2797.0,
           pwmDown='hpg.pwmgen.00.out.02',
           pwmUp='hpg.pwmgen.00.out.03',
           enableDown='bb_gpio.p8.out-38',
           enableUp='bb_gpio.p8.out-40')

setupGyro()
setupPosPid()

hal.addf('hpg.update', baseThread)
hal.addf('bb_gpio.write', baseThread)

hal.start_threads()
#include "include.h"

#include "bk_timer_pub.h"
#include "drv_model_pub.h"
#include "fake_clock_pub.h"
#include "icu_pub.h"
#include "mcu_ps_pub.h"
#include "power_save_pub.h"
#include "pwm_pub.h"
#include "rtos_pub.h"
#include "sys_rtos.h"
#include "task.h"
#include "uart_pub.h"

// the microsecond timer for micros() (LibreTiny lt_config.h BEKEN_MICROS_HIGH_RES, on for the BK7231N)
#if !defined(BEKEN_MICROS_HIGH_RES) && 1
#define BEKEN_MICROS_HIGH_RES 1
#endif

// main FreeRTOS timer ID
static BK_HW_TIMER_INDEX fclk_id = BK_PWM_TIMER_ID0;

extern UINT32 bk_cal_init(UINT32 setting);
extern void mcu_ps_increase_clr(void);
// the switch an interrupt over an interrupt postponed to this tick (the kernel package portable/GCC/ARM968/port.c vPortYieldFromIsr)
extern uint32_t preempt_delayed_schedule_get_flag(void);
extern void preempt_delayed_schedule_clear_flag(void);

// forward definitions
static void fclk_timer_hw_init(BK_HW_TIMER_INDEX timer_id);
static void fclk_hdl(UINT8 param);

void fclk_init(void) {
#if (CFG_SOC_NAME == SOC_BK7231)
	fclk_timer_hw_init(BK_PWM_TIMER_ID3);
#elif BEKEN_MICROS_HIGH_RES
	fclk_timer_hw_init(BK_TIMER_ID0);
#else
	fclk_timer_hw_init(BK_TIMER_ID3);
#endif

#if CFG_USE_TICK_CAL
	bk_cal_init(0);
#endif
}

/* timer_id: BK_PWM_TIMER_ID0 or BK_TIMER_ID3 */
static void fclk_timer_hw_init(BK_HW_TIMER_INDEX timer_id) {
#if (CFG_SOC_NAME == SOC_BK7231)
	ASSERT(timer_id >= BK_PWM_TIMER_ID0);
#endif

	fclk_id = timer_id;
	if (fclk_id >= BK_PWM_TIMER_ID0) { // pwm timer
		pwm_param_t param;
		param.channel		  = (fclk_id - BK_PWM_TIMER_ID0);
		param.cfg.bits.en	  = PWM_ENABLE;
		param.cfg.bits.int_en = PWM_INT_EN;
		param.cfg.bits.mode	  = PWM_TIMER_MODE;
		param.cfg.bits.clk	  = PWM_CLK_26M;
		param.p_Int_Handler	  = fclk_hdl;
#if (CFG_SOC_NAME == SOC_BK7231N) || (CFG_SOC_NAME == SOC_BK7238) || (CFG_SOC_NAME == SOC_BK7252N)
		param.duty_cycle1 = 0;
#else
		param.duty_cycle = 0;
#endif
		param.end_value = fclk_cal_endvalue((UINT32)param.cfg.bits.clk);

#if CFG_BDK_USE_NEW_PWM_DRIVER
		// should never be true, since the PWM timer is only used on BK7231Q
		os_printf("Fake clock with PWM timer not implemented on BK7231N
");
#else
		sddev_control(PWM_DEV_NAME, CMD_PWM_INIT_PARAM, &param);
#endif
	} else { // timer
		timer_param_t param;
		param.channel = fclk_id;
		param.div	  = 1;
#if BEKEN_MICROS_HIGH_RES
		param.period = FCLK_DURATION_MS * 1000;
#else
		param.period = FCLK_DURATION_MS;
#endif
		param.t_Int_Handler = fclk_hdl;

#if BEKEN_MICROS_HIGH_RES
		UINT32 ret = sddev_control(TIMER_DEV_NAME, CMD_TIMER_INIT_PARAM_US, &param);
#else
		UINT32 ret = sddev_control(TIMER_DEV_NAME, CMD_TIMER_INIT_PARAM, &param);
#endif
		ASSERT(BK_TIMER_SUCCESS == ret);
		sddev_control(TIMER_DEV_NAME, CMD_TIMER_UNIT_ENABLE, &param.channel);
	}
}

static void fclk_hdl(UINT8 param) {
#if CFG_USE_TICK_CAL && !CFG_LOW_VOLTAGE_PS
	if (!mcu_ps_need_pstick())
		return;
#endif
	GLOBAL_INT_DECLARATION();
	GLOBAL_INT_DISABLE();
	// FreeRTOS-Kernel V11 (its vTaskSwitchContext() is not the BDK's patched one): the switch through the port, which
	// postpones it again when this handler interrupted another interrupt
	if (xTaskIncrementTick() != pdFALSE || preempt_delayed_schedule_get_flag()) {
		preempt_delayed_schedule_clear_flag();
		vPortYieldFromIsr();
	}

	GLOBAL_INT_RESTORE();
}

// The ticks lost while the timer could not count (the MCU power save, the calibration of clock_cal.c from its timer
// interrupt): one by one through the kernel's tick, as the ESP8266 port does. vTaskStepTick() of FreeRTOS-Kernel V11 is
// only for the tickless idle with the scheduler suspended and asserts it never jumps past the next unblock time;
// xTaskIncrementTick() is right from an interrupt, and with the scheduler suspended (the idle task's tickless sleep) it
// counts the ticks as pended, xTaskResumeAll() catches them up
UINT32 fclk_update_tick(UINT32 tick) {
	GLOBAL_INT_DECLARATION();
	BaseType_t switch_required = pdFALSE;
	if (tick == 0)
		return 0;
	GLOBAL_INT_DISABLE();
#if CFG_USE_TICK_CAL && !CFG_LOW_VOLTAGE_PS
	mcu_ps_increase_clr();
#endif
	while (tick--) {
		if (xTaskIncrementTick() != pdFALSE) {
			switch_required = pdTRUE;
		}
	}
	if (switch_required != pdFALSE) {
		if (platform_is_in_interrupt_context()) {
			vPortYieldFromIsr();
		} else if (xTaskGetSchedulerState() == taskSCHEDULER_RUNNING) {
			portYIELD();
		}
	}
	GLOBAL_INT_RESTORE();
	return 0;
}

UINT64 fclk_get_tick(void) {
	return xTaskGetTickCount();
}

UINT32 fclk_get_second(void) {
	return xTaskGetTickCount() / FCLK_SECOND;
}

BK_HW_TIMER_INDEX fclk_get_tick_id(void) {
	return fclk_id;
}

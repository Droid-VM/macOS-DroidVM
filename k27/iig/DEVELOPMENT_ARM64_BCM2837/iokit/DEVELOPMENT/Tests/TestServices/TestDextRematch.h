/* iig(DriverKit-427.100.5) generated from TestDextRematch.iig */

/* TestDextRematch.iig:1-28 */
/*
 * Copyright (c) 2025 Apple Computer, Inc. All rights reserved.
 *
 * @APPLE_LICENSE_HEADER_START@
 *
 * The contents of this file constitute Original Code as defined in and
 * are subject to the Apple Public Source License Version 1.1 (the
 * "License").  You may not use this file except in compliance with the
 * License.  Please obtain a copy of the License at
 * http://www.apple.com/publicsource and read it before using this file.
 *
 * This Original Code and all software distributed under the License are
 * distributed on an "AS IS" basis, WITHOUT WARRANTY OF ANY KIND, EITHER
 * EXPRESS OR IMPLIED, AND APPLE HEREBY DISCLAIMS ALL SUCH WARRANTIES,
 * INCLUDING WITHOUT LIMITATION, ANY WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE OR NON-INFRINGEMENT.  Please see the
 * License for the specific language governing rights and limitations
 * under the License.
 *
 * @APPLE_LICENSE_HEADER_END@
 */

#ifndef TestDextRematch_h
#define TestDextRematch_h

#include <Availability.h>
#include <DriverKit/IOService.h>  /* .iig include */

/* source class TestDextRematch TestDextRematch.iig:29-49 */

#if __DOCUMENTATION__
#define KERNEL IIG_KERNEL

/*!
 @iig implementation
 #if KERNEL
 #include "Tests/TestServices/TestDextRematchKernel.h"
 #endif
 @iig end
 */

class KERNEL TestDextRematch : public IOService
{
public:
	virtual void free() override;

	virtual kern_return_t
	Start(IOService * provider) LOCAL override;

	virtual kern_return_t
	Stop(IOService * provider) LOCAL override;

	virtual bool
	ShouldStartFail();
};

#undef KERNEL
#else /* __DOCUMENTATION__ */

/* generated class TestDextRematch TestDextRematch.iig:29-49 */

#define TestDextRematch_ShouldStartFail_ID            0xb92798a9490ba56eULL

#define TestDextRematch_Start_Args \
        IOService * provider

#define TestDextRematch_Stop_Args \
        IOService * provider

#define TestDextRematch_ShouldStartFail_Args \


#define TestDextRematch_Methods \
\
public:\
\
    virtual kern_return_t\
    Dispatch(const IORPC rpc) APPLE_KEXT_OVERRIDE;\
\
    static kern_return_t\
    _Dispatch(TestDextRematch * self, const IORPC rpc);\
\
    bool\
    ShouldStartFail(\
        OSDispatchMethod supermethod = NULL);\
\
\
protected:\
    /* _Impl methods */\
\
    kern_return_t\
    Start_Impl(IOService_Start_Args);\
\
    kern_return_t\
    Stop_Impl(IOService_Stop_Args);\
\
\
public:\
    /* _Invoke methods */\
\
    typedef bool (*ShouldStartFail_Handler)(OSMetaClassBase * targetTestDextRematch_ShouldStartFail_Args);\
    static kern_return_t\
    ShouldStartFail_Invoke(const IORPC rpc,\
        OSMetaClassBase * target,\
        ShouldStartFail_Handler func);\
\


#define TestDextRematch_KernelMethods \
\
protected:\
    /* _Impl methods */\
\
    bool\
    ShouldStartFail_Impl(TestDextRematch_ShouldStartFail_Args);\
\


#define TestDextRematch_VirtualMethods \
\
public:\
\
    virtual void\
    free(\
) APPLE_KEXT_OVERRIDE;\
\


#if !KERNEL

extern OSMetaClass          * gTestDextRematchMetaClass;
extern const OSClassLoadInformation TestDextRematch_Class;

class TestDextRematchMetaClass : public OSMetaClass
{
public:
    virtual kern_return_t
    New(OSObject * instance) override;
    virtual kern_return_t
    Dispatch(const IORPC rpc) override;
};

#endif /* !KERNEL */

#if !KERNEL

class  TestDextRematchInterface : public OSInterface
{
public:
};

struct TestDextRematch_IVars;
struct TestDextRematch_LocalIVars;

class TestDextRematch : public IOService, public TestDextRematchInterface
{
#if !KERNEL
    friend class TestDextRematchMetaClass;
#endif /* !KERNEL */

#if !KERNEL
public:
#ifdef TestDextRematch_DECLARE_IVARS
TestDextRematch_DECLARE_IVARS
#else /* TestDextRematch_DECLARE_IVARS */
    union
    {
        TestDextRematch_IVars * ivars;
        TestDextRematch_LocalIVars * lvars;
    };
#endif /* TestDextRematch_DECLARE_IVARS */
#endif /* !KERNEL */

#if !KERNEL
    static OSMetaClass *
    sGetMetaClass() { return gTestDextRematchMetaClass; };
#endif /* KERNEL */

    using super = IOService;

#if !KERNEL
    TestDextRematch_Methods
    TestDextRematch_VirtualMethods
#endif /* !KERNEL */

};
#endif /* !KERNEL */


#endif /* !__DOCUMENTATION__ */

/* TestDextRematch.iig:51- */

#endif /* TestDextRematch_h */

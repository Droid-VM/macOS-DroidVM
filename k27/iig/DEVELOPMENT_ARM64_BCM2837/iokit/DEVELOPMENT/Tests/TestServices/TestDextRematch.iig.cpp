#if DEBUG || DEVELOPMENT
/* iig(DriverKit-427.100.5 Apr 30 2025 01:57:02) generated from TestDextRematch.iig */

#undef	IIG_IMPLEMENTATION
#define	IIG_IMPLEMENTATION 	TestDextRematch.iig

#if KERNEL
#include <libkern/c++/OSString.h>
#else
#include <DriverKit/DriverKit.h>
#endif /* KERNEL */
#include <DriverKit/IOReturn.h>
#include "TestDextRematch.h"

/* @iig implementation */
 #if KERNEL
 #include "Tests/TestServices/TestDextRematchKernel.h"
 #endif
 /* @iig end */


#if __has_builtin(__builtin_load_member_function_pointer)
#define SimpleMemberFunctionCast(cfnty, self, func) (cfnty)__builtin_load_member_function_pointer(self, func)
#else
#define SimpleMemberFunctionCast(cfnty, self, func) ({ union { typeof(func) memfun; cfnty cfun; } pair; pair.memfun = func; pair.cfun; })
#endif


struct TestDextRematch_ShouldStartFail_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
};
#pragma pack(4)
struct TestDextRematch_ShouldStartFail_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
};
struct TestDextRematch_ShouldStartFail_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    TestDextRematch_ShouldStartFail_Msg_Content content;
};
#pragma pack()
#define TestDextRematch_ShouldStartFail_Msg_ObjRefs (1)

struct TestDextRematch_ShouldStartFail_Rpl_Content
{
    IORPCMessage __hdr;
};
#pragma pack(4)
struct TestDextRematch_ShouldStartFail_Rpl
{
    IORPCMessageMach           mach;
};
struct TestDextRematch_ShouldStartFail_Rpl_With_Content
{
    IORPCMessageMach           mach;
    TestDextRematch_ShouldStartFail_Rpl_Content content;
};
#pragma pack()
#define TestDextRematch_ShouldStartFail_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct TestDextRematch_ShouldStartFail_Msg * message;
#else /* KERNEL */
        const struct TestDextRematch_ShouldStartFail_Msg_With_Content * message;
#endif /* KERNEL */
        struct TestDextRematch_ShouldStartFail_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct TestDextRematch_ShouldStartFail_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} TestDextRematch_ShouldStartFail_Invocation;
#if !KERNEL
extern OSMetaClass * gOSContainerMetaClass;
extern OSMetaClass * gOSDataMetaClass;
extern OSMetaClass * gOSNumberMetaClass;
extern OSMetaClass * gOSStringMetaClass;
extern OSMetaClass * gOSBooleanMetaClass;
extern OSMetaClass * gOSDictionaryMetaClass;
extern OSMetaClass * gOSArrayMetaClass;
extern OSMetaClass * gOSSetMetaClass;
extern OSMetaClass * gOSOrderedSetMetaClass;
extern OSMetaClass * gIODispatchQueueMetaClass;
extern OSMetaClass * gIOMemoryDescriptorMetaClass;
extern OSMetaClass * gIOBufferMemoryDescriptorMetaClass;
extern OSMetaClass * gIOUserClientMetaClass;
extern OSMetaClass * gOSActionMetaClass;
extern OSMetaClass * gIOServiceStateNotificationDispatchSourceMetaClass;
#endif /* !KERNEL */

#if !KERNEL

#define TestDextRematch_QueueNames  ""

#define TestDextRematch_MethodNames  ""

#define TestDextRematchMetaClass_MethodNames  ""

struct OSClassDescription_TestDextRematch_t
{
    OSClassDescription base;
    uint64_t           methodOptions[2 * 0];
    uint64_t           metaMethodOptions[2 * 0];
    char               queueNames[sizeof(TestDextRematch_QueueNames)];
    char               methodNames[sizeof(TestDextRematch_MethodNames)];
    char               metaMethodNames[sizeof(TestDextRematchMetaClass_MethodNames)];
};

const struct OSClassDescription_TestDextRematch_t
OSClassDescription_TestDextRematch =
{
    .base =
    {
        .descriptionSize         = sizeof(OSClassDescription_TestDextRematch_t),
        .name                    = "TestDextRematch",
        .superName               = "IOService",
        .methodOptionsSize       = 2 * sizeof(uint64_t) * 0,
        .methodOptionsOffset     = __builtin_offsetof(struct OSClassDescription_TestDextRematch_t, methodOptions),
        .metaMethodOptionsSize   = 2 * sizeof(uint64_t) * 0,
        .metaMethodOptionsOffset = __builtin_offsetof(struct OSClassDescription_TestDextRematch_t, metaMethodOptions),
        .queueNamesSize       = sizeof(TestDextRematch_QueueNames),
        .queueNamesOffset     = __builtin_offsetof(struct OSClassDescription_TestDextRematch_t, queueNames),
        .methodNamesSize         = sizeof(TestDextRematch_MethodNames),
        .methodNamesOffset       = __builtin_offsetof(struct OSClassDescription_TestDextRematch_t, methodNames),
        .metaMethodNamesSize     = sizeof(TestDextRematchMetaClass_MethodNames),
        .metaMethodNamesOffset   = __builtin_offsetof(struct OSClassDescription_TestDextRematch_t, metaMethodNames),
        .flags                   = 1*kOSClassCanRemote,
        .resv1                   = {0},
    },
    .methodOptions =
    {
    },
    .metaMethodOptions =
    {
    },
    .queueNames      = TestDextRematch_QueueNames,
    .methodNames     = TestDextRematch_MethodNames,
    .metaMethodNames = TestDextRematchMetaClass_MethodNames,
};

OSMetaClass * gTestDextRematchMetaClass;

static kern_return_t
TestDextRematch_New(OSMetaClass * instance);

const OSClassLoadInformation
TestDextRematch_Class = 
{
    .description       = &OSClassDescription_TestDextRematch.base,
    .metaPointer       = &gTestDextRematchMetaClass,
    .version           = 1,
    .instanceSize      = sizeof(TestDextRematch),

    .resv2             = {0},

    .New               = &TestDextRematch_New,
    .resv3             = {0},

};

extern const void * const
gTestDextRematch_Declaration;
const void * const
gTestDextRematch_Declaration
__attribute__((used,visibility("hidden"),section("__DATA_CONST,__osclassinfo,regular,no_dead_strip"),no_sanitize("address")))
    = &TestDextRematch_Class;

static kern_return_t
TestDextRematch_New(OSMetaClass * instance)
{
    if (!new(instance) TestDextRematchMetaClass) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

kern_return_t
TestDextRematchMetaClass::New(OSObject * instance)
{
    if (!new(instance) TestDextRematch) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

#endif /* !KERNEL */

#ifdef KERNEL
#define MESSAGE_CONTENT(__field) (messageContent->__field)
#else /* KERNEL */
#define MESSAGE_CONTENT(__field) (message->content.__field)
#endif /* KERNEL */

kern_return_t
TestDextRematch::Dispatch(const IORPC rpc)
{
    return _Dispatch(this, rpc);
}

kern_return_t
TestDextRematch::_Dispatch(TestDextRematch * self, const IORPC rpc)
{
    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {
        case IOService_Start_ID:
        {
            ret = IOService::Start_Invoke(rpc, self, SimpleMemberFunctionCast(IOService::Start_Handler, *self, &TestDextRematch::Start_Impl));
            break;
        }
        case IOService_Stop_ID:
        {
            ret = IOService::Stop_Invoke(rpc, self, SimpleMemberFunctionCast(IOService::Stop_Handler, *self, &TestDextRematch::Stop_Impl));
            break;
        }
#if KERNEL
        case TestDextRematch_ShouldStartFail_ID:
        {
            ret = TestDextRematch::ShouldStartFail_Invoke(rpc, self, SimpleMemberFunctionCast(TestDextRematch::ShouldStartFail_Handler, *self, &TestDextRematch::ShouldStartFail_Impl));
            break;
        }
#endif /* !KERNEL */

        default:
            ret = IOService::_Dispatch(self, rpc);
            break;
    }

    return (ret);
}

#if KERNEL
kern_return_t
TestDextRematch::MetaClass::Dispatch(const IORPC rpc)
{
#else /* KERNEL */
kern_return_t
TestDextRematchMetaClass::Dispatch(const IORPC rpc)
{
#endif /* !KERNEL */

    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {

        default:
            ret = OSMetaClassBase::Dispatch(rpc);
            break;
    }

    return (ret);
}

bool
TestDextRematch::ShouldStartFail(        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        TestDextRematch_ShouldStartFail_Msg_With_Content msg;
        struct
        {
            TestDextRematch_ShouldStartFail_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct TestDextRematch_ShouldStartFail_Msg_With_Content * msg = &buf.msg;
    struct TestDextRematch_ShouldStartFail_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = TestDextRematch_ShouldStartFail_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = TestDextRematch_ShouldStartFail_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 1;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != TestDextRematch_ShouldStartFail_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 0) { ret = kIOReturnIPCError; break; };
            if (TestDextRematch_ShouldStartFail_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
    }


    return (ret);
}

kern_return_t
TestDextRematch::ShouldStartFail_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        ShouldStartFail_Handler func)
{
    TestDextRematch_ShouldStartFail_Invocation rpc = { _rpc };
    TestDextRematch_ShouldStartFail_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const TestDextRematch_ShouldStartFail_Msg *         message = rpc.message;
    const TestDextRematch_ShouldStartFail_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const TestDextRematch_ShouldStartFail_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;

    if (1 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (TestDextRematch_ShouldStartFail_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(TestDextRematch_ShouldStartFail_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);

    ret = (*func)(target);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = TestDextRematch_ShouldStartFail_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 0;
    reply->content.__hdr.objectRefs = TestDextRematch_ShouldStartFail_Rpl_ObjRefs;

    return (ret);
}



#endif

/* iig(DriverKit-427.100.5 Apr 30 2025 01:57:02) generated from IOInterruptDispatchSource.iig */

#undef	IIG_IMPLEMENTATION
#define	IIG_IMPLEMENTATION 	IOInterruptDispatchSource.iig

#if KERNEL
#include <libkern/c++/OSString.h>
#else
#include <DriverKit/DriverKit.h>
#endif /* KERNEL */
#include <DriverKit/IOReturn.h>
#include <DriverKit/IOInterruptDispatchSource.h>


#if __has_builtin(__builtin_load_member_function_pointer)
#define SimpleMemberFunctionCast(cfnty, self, func) (cfnty)__builtin_load_member_function_pointer(self, func)
#else
#define SimpleMemberFunctionCast(cfnty, self, func) OSMemberFunctionCast(cfnty, &(self), func)
#endif


struct IOInterruptDispatchSource_Create_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSObjectRef  provider;
    OSObjectRef  queue;
    uint32_t  index;
};
#pragma pack(4)
struct IOInterruptDispatchSource_Create_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t provider__descriptor;
    mach_msg_port_descriptor_t queue__descriptor;
};
struct IOInterruptDispatchSource_Create_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t provider__descriptor;
    mach_msg_port_descriptor_t queue__descriptor;
    IOInterruptDispatchSource_Create_Msg_Content content;
};
#pragma pack()
#define IOInterruptDispatchSource_Create_Msg_ObjRefs (3)

struct IOInterruptDispatchSource_Create_Rpl_Content
{
    IORPCMessage __hdr;
    OSObjectRef  source;
};
#pragma pack(4)
struct IOInterruptDispatchSource_Create_Rpl
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t source__descriptor;
};
struct IOInterruptDispatchSource_Create_Rpl_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t source__descriptor;
    IOInterruptDispatchSource_Create_Rpl_Content content;
};
#pragma pack()
#define IOInterruptDispatchSource_Create_Rpl_ObjRefs (1)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOInterruptDispatchSource_Create_Msg * message;
#else /* KERNEL */
        const struct IOInterruptDispatchSource_Create_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOInterruptDispatchSource_Create_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOInterruptDispatchSource_Create_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOInterruptDispatchSource_Create_Invocation;
struct IOInterruptDispatchSource_GetInterruptType_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSObjectRef  provider;
    uint32_t  index;
};
#pragma pack(4)
struct IOInterruptDispatchSource_GetInterruptType_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t provider__descriptor;
};
struct IOInterruptDispatchSource_GetInterruptType_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t provider__descriptor;
    IOInterruptDispatchSource_GetInterruptType_Msg_Content content;
};
#pragma pack()
#define IOInterruptDispatchSource_GetInterruptType_Msg_ObjRefs (2)

struct IOInterruptDispatchSource_GetInterruptType_Rpl_Content
{
    IORPCMessage __hdr;
    unsigned long long  interruptType;
};
#pragma pack(4)
struct IOInterruptDispatchSource_GetInterruptType_Rpl
{
    IORPCMessageMach           mach;
};
struct IOInterruptDispatchSource_GetInterruptType_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IOInterruptDispatchSource_GetInterruptType_Rpl_Content content;
};
#pragma pack()
#define IOInterruptDispatchSource_GetInterruptType_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOInterruptDispatchSource_GetInterruptType_Msg * message;
#else /* KERNEL */
        const struct IOInterruptDispatchSource_GetInterruptType_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOInterruptDispatchSource_GetInterruptType_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOInterruptDispatchSource_GetInterruptType_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOInterruptDispatchSource_GetInterruptType_Invocation;
struct IOInterruptDispatchSource_SetHandler_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSObjectRef  action;
};
#pragma pack(4)
struct IOInterruptDispatchSource_SetHandler_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t action__descriptor;
};
struct IOInterruptDispatchSource_SetHandler_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t action__descriptor;
    IOInterruptDispatchSource_SetHandler_Msg_Content content;
};
#pragma pack()
#define IOInterruptDispatchSource_SetHandler_Msg_ObjRefs (2)

struct IOInterruptDispatchSource_SetHandler_Rpl_Content
{
    IORPCMessage __hdr;
};
#pragma pack(4)
struct IOInterruptDispatchSource_SetHandler_Rpl
{
    IORPCMessageMach           mach;
};
struct IOInterruptDispatchSource_SetHandler_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IOInterruptDispatchSource_SetHandler_Rpl_Content content;
};
#pragma pack()
#define IOInterruptDispatchSource_SetHandler_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOInterruptDispatchSource_SetHandler_Msg * message;
#else /* KERNEL */
        const struct IOInterruptDispatchSource_SetHandler_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOInterruptDispatchSource_SetHandler_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOInterruptDispatchSource_SetHandler_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOInterruptDispatchSource_SetHandler_Invocation;
struct IOInterruptDispatchSource_GetLastInterrupt_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
};
#pragma pack(4)
struct IOInterruptDispatchSource_GetLastInterrupt_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
};
struct IOInterruptDispatchSource_GetLastInterrupt_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    IOInterruptDispatchSource_GetLastInterrupt_Msg_Content content;
};
#pragma pack()
#define IOInterruptDispatchSource_GetLastInterrupt_Msg_ObjRefs (1)

struct IOInterruptDispatchSource_GetLastInterrupt_Rpl_Content
{
    IORPCMessage __hdr;
    unsigned long long  count;
    unsigned long long  time;
};
#pragma pack(4)
struct IOInterruptDispatchSource_GetLastInterrupt_Rpl
{
    IORPCMessageMach           mach;
};
struct IOInterruptDispatchSource_GetLastInterrupt_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IOInterruptDispatchSource_GetLastInterrupt_Rpl_Content content;
};
#pragma pack()
#define IOInterruptDispatchSource_GetLastInterrupt_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOInterruptDispatchSource_GetLastInterrupt_Msg * message;
#else /* KERNEL */
        const struct IOInterruptDispatchSource_GetLastInterrupt_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOInterruptDispatchSource_GetLastInterrupt_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOInterruptDispatchSource_GetLastInterrupt_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOInterruptDispatchSource_GetLastInterrupt_Invocation;
struct IOInterruptDispatchSource_InterruptOccurred_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSObjectRef  action;
    uint64_t  count;
    uint64_t  time;
};
#pragma pack(4)
struct IOInterruptDispatchSource_InterruptOccurred_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t action__descriptor;
};
struct IOInterruptDispatchSource_InterruptOccurred_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t action__descriptor;
    IOInterruptDispatchSource_InterruptOccurred_Msg_Content content;
};
#pragma pack()
#define IOInterruptDispatchSource_InterruptOccurred_Msg_ObjRefs (2)

struct IOInterruptDispatchSource_InterruptOccurred_Rpl_Content
{
    IORPCMessage __hdr;
};
#pragma pack(4)
struct IOInterruptDispatchSource_InterruptOccurred_Rpl
{
    IORPCMessageMach           mach;
};
struct IOInterruptDispatchSource_InterruptOccurred_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IOInterruptDispatchSource_InterruptOccurred_Rpl_Content content;
};
#pragma pack()
#define IOInterruptDispatchSource_InterruptOccurred_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOInterruptDispatchSource_InterruptOccurred_Msg * message;
#else /* KERNEL */
        const struct IOInterruptDispatchSource_InterruptOccurred_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOInterruptDispatchSource_InterruptOccurred_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOInterruptDispatchSource_InterruptOccurred_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOInterruptDispatchSource_InterruptOccurred_Invocation;
#if !KERNEL
extern OSMetaClass * gOSContainerMetaClass;
extern OSMetaClass * gOSDataMetaClass;
extern OSMetaClass * gOSNumberMetaClass;
extern OSMetaClass * gOSBooleanMetaClass;
extern OSMetaClass * gOSDictionaryMetaClass;
extern OSMetaClass * gOSArrayMetaClass;
extern OSMetaClass * gOSSetMetaClass;
extern OSMetaClass * gOSOrderedSetMetaClass;
extern OSMetaClass * gOSStringMetaClass;
extern OSMetaClass * gIOMemoryDescriptorMetaClass;
extern OSMetaClass * gIOBufferMemoryDescriptorMetaClass;
extern OSMetaClass * gIOUserClientMetaClass;
extern OSMetaClass * gIOServiceStateNotificationDispatchSourceMetaClass;
#endif /* !KERNEL */

#if KERNEL
OSDefineMetaClassAndStructors(IOInterruptDispatchSource, IODispatchSource);
#endif /* KERNEL */

#if !KERNEL

#define IOInterruptDispatchSource_QueueNames  ""

#define IOInterruptDispatchSource_MethodNames  ""

#define IOInterruptDispatchSourceMetaClass_MethodNames  ""

struct OSClassDescription_IOInterruptDispatchSource_t
{
    OSClassDescription base;
    uint64_t           methodOptions[2 * 0];
    uint64_t           metaMethodOptions[2 * 0];
    char               queueNames[sizeof(IOInterruptDispatchSource_QueueNames)];
    char               methodNames[sizeof(IOInterruptDispatchSource_MethodNames)];
    char               metaMethodNames[sizeof(IOInterruptDispatchSourceMetaClass_MethodNames)];
};

const struct OSClassDescription_IOInterruptDispatchSource_t
OSClassDescription_IOInterruptDispatchSource =
{
    .base =
    {
        .descriptionSize         = sizeof(OSClassDescription_IOInterruptDispatchSource_t),
        .name                    = "IOInterruptDispatchSource",
        .superName               = "IODispatchSource",
        .methodOptionsSize       = 2 * sizeof(uint64_t) * 0,
        .methodOptionsOffset     = __builtin_offsetof(struct OSClassDescription_IOInterruptDispatchSource_t, methodOptions),
        .metaMethodOptionsSize   = 2 * sizeof(uint64_t) * 0,
        .metaMethodOptionsOffset = __builtin_offsetof(struct OSClassDescription_IOInterruptDispatchSource_t, metaMethodOptions),
        .queueNamesSize       = sizeof(IOInterruptDispatchSource_QueueNames),
        .queueNamesOffset     = __builtin_offsetof(struct OSClassDescription_IOInterruptDispatchSource_t, queueNames),
        .methodNamesSize         = sizeof(IOInterruptDispatchSource_MethodNames),
        .methodNamesOffset       = __builtin_offsetof(struct OSClassDescription_IOInterruptDispatchSource_t, methodNames),
        .metaMethodNamesSize     = sizeof(IOInterruptDispatchSourceMetaClass_MethodNames),
        .metaMethodNamesOffset   = __builtin_offsetof(struct OSClassDescription_IOInterruptDispatchSource_t, metaMethodNames),
        .flags                   = 1*kOSClassCanRemote,
        .resv1                   = {0},
    },
    .methodOptions =
    {
    },
    .metaMethodOptions =
    {
    },
    .queueNames      = IOInterruptDispatchSource_QueueNames,
    .methodNames     = IOInterruptDispatchSource_MethodNames,
    .metaMethodNames = IOInterruptDispatchSourceMetaClass_MethodNames,
};

OSMetaClass * gIOInterruptDispatchSourceMetaClass;

static kern_return_t
IOInterruptDispatchSource_New(OSMetaClass * instance);

const OSClassLoadInformation
IOInterruptDispatchSource_Class = 
{
    .description       = &OSClassDescription_IOInterruptDispatchSource.base,
    .metaPointer       = &gIOInterruptDispatchSourceMetaClass,
    .version           = 1,
    .instanceSize      = sizeof(IOInterruptDispatchSource),

    .resv2             = {0},

    .New               = &IOInterruptDispatchSource_New,
    .resv3             = {0},

};

extern const void * const
gIOInterruptDispatchSource_Declaration;
const void * const
gIOInterruptDispatchSource_Declaration
__attribute__((used,visibility("hidden"),section("__DATA_CONST,__osclassinfo,regular,no_dead_strip"),no_sanitize("address")))
    = &IOInterruptDispatchSource_Class;

static kern_return_t
IOInterruptDispatchSource_New(OSMetaClass * instance)
{
    if (!new(instance) IOInterruptDispatchSourceMetaClass) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

kern_return_t
IOInterruptDispatchSourceMetaClass::New(OSObject * instance)
{
    if (!new(instance) IOInterruptDispatchSource) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

#endif /* !KERNEL */

#ifdef KERNEL
#define MESSAGE_CONTENT(__field) (messageContent->__field)
#else /* KERNEL */
#define MESSAGE_CONTENT(__field) (message->content.__field)
#endif /* KERNEL */

kern_return_t
IOInterruptDispatchSource::Dispatch(const IORPC rpc)
{
    return _Dispatch(this, rpc);
}

kern_return_t
IOInterruptDispatchSource::_Dispatch(IOInterruptDispatchSource * self, const IORPC rpc)
{
    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {
        case IOInterruptDispatchSource_SetHandler_ID:
        {
            ret = IOInterruptDispatchSource::SetHandler_Invoke(rpc, self, SimpleMemberFunctionCast(IOInterruptDispatchSource::SetHandler_Handler, *self, &IOInterruptDispatchSource::SetHandler_Impl));
            break;
        }
        case IODispatchSource_SetEnableWithCompletion_ID:
        {
            ret = IODispatchSource::SetEnableWithCompletion_Invoke(rpc, self, SimpleMemberFunctionCast(IODispatchSource::SetEnableWithCompletion_Handler, *self, &IOInterruptDispatchSource::SetEnableWithCompletion_Impl));
            break;
        }
        case IODispatchSource_Cancel_ID:
        {
            ret = IODispatchSource::Cancel_Invoke(rpc, self, SimpleMemberFunctionCast(IODispatchSource::Cancel_Handler, *self, &IOInterruptDispatchSource::Cancel_Impl));
            break;
        }
#if KERNEL
        case IOInterruptDispatchSource_GetLastInterrupt_ID:
        {
            ret = IOInterruptDispatchSource::GetLastInterrupt_Invoke(rpc, self, SimpleMemberFunctionCast(IOInterruptDispatchSource::GetLastInterrupt_Handler, *self, &IOInterruptDispatchSource::GetLastInterrupt_Impl));
            break;
        }
#endif /* !KERNEL */
        case IODispatchSource_CheckForWork_ID:
        {
            ret = IODispatchSource::CheckForWork_Invoke(rpc, self, SimpleMemberFunctionCast(IODispatchSource::CheckForWork_Handler, *self, &IOInterruptDispatchSource::CheckForWork_Impl));
            break;
        }
        case IOInterruptDispatchSource_InterruptOccurred_ID:
        {
            ret = IOInterruptDispatchSource::InterruptOccurred_Invoke(rpc, self, SimpleMemberFunctionCast(IOInterruptDispatchSource::InterruptOccurred_Handler, *self, &IOInterruptDispatchSource::InterruptOccurred_Impl));
            break;
        }

        default:
            ret = IODispatchSource::_Dispatch(self, rpc);
            break;
    }

    return (ret);
}

#if KERNEL
kern_return_t
IOInterruptDispatchSource::MetaClass::Dispatch(const IORPC rpc)
{
#else /* KERNEL */
kern_return_t
IOInterruptDispatchSourceMetaClass::Dispatch(const IORPC rpc)
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
#if KERNEL
        case IOInterruptDispatchSource_Create_ID:
            ret = IOInterruptDispatchSource::Create_Invoke(rpc, &IOInterruptDispatchSource::Create_Impl);
            break;
#endif /* !KERNEL */
#if KERNEL
        case IOInterruptDispatchSource_GetInterruptType_ID:
            ret = IOInterruptDispatchSource::GetInterruptType_Invoke(rpc, &IOInterruptDispatchSource::GetInterruptType_Impl);
            break;
#endif /* !KERNEL */

        default:
            ret = OSMetaClassBase::Dispatch(rpc);
            break;
    }

    return (ret);
}

kern_return_t
IOInterruptDispatchSource::Create_Call(
        IOService * provider,
        uint32_t index,
        IODispatchQueue * queue,
        IOInterruptDispatchSource ** source)
{
    kern_return_t ret;
    union
    {
        IOInterruptDispatchSource_Create_Msg_With_Content msg;
        struct
        {
            IOInterruptDispatchSource_Create_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOInterruptDispatchSource_Create_Msg_With_Content * msg = &buf.msg;
    struct IOInterruptDispatchSource_Create_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 0*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOInterruptDispatchSource_Create_ID;
    msg->content.__object = (OSObjectRef) OSTypeID(IOInterruptDispatchSource);
    msg->content.__hdr.objectRefs = IOInterruptDispatchSource_Create_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 3;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->provider__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.provider = (OSObjectRef) provider;

    msg->content.index = index;

    msg->queue__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.queue = (OSObjectRef) queue;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    ret = OSMTypeID(IOInterruptDispatchSource)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOInterruptDispatchSource_Create_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 1) { ret = kIOReturnIPCError; break; };
            if (IOInterruptDispatchSource_Create_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        *source = OSDynamicCast(IOInterruptDispatchSource, (OSObject *) rpl->content.source);
        if (rpl->content.source && !*source) ret = kIOReturnBadArgument;
    }


    return (ret);
}

kern_return_t
IOInterruptDispatchSource::GetInterruptType(
        IOService * provider,
        uint32_t index,
        uint64_t * interruptType)
{
    kern_return_t ret;
    union
    {
        IOInterruptDispatchSource_GetInterruptType_Msg_With_Content msg;
        struct
        {
            IOInterruptDispatchSource_GetInterruptType_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOInterruptDispatchSource_GetInterruptType_Msg_With_Content * msg = &buf.msg;
    struct IOInterruptDispatchSource_GetInterruptType_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOInterruptDispatchSource_GetInterruptType_ID;
    msg->content.__object = (OSObjectRef) OSTypeID(IOInterruptDispatchSource);
    msg->content.__hdr.objectRefs = IOInterruptDispatchSource_GetInterruptType_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 2;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->provider__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.provider = (OSObjectRef) provider;

    msg->content.index = index;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    ret = OSMTypeID(IOInterruptDispatchSource)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOInterruptDispatchSource_GetInterruptType_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 0) { ret = kIOReturnIPCError; break; };
            if (IOInterruptDispatchSource_GetInterruptType_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        if (interruptType) *interruptType = rpl->content.interruptType;
    }


    return (ret);
}

kern_return_t
IOInterruptDispatchSource::SetHandler(
        OSAction * action,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOInterruptDispatchSource_SetHandler_Msg_With_Content msg;
        struct
        {
            IOInterruptDispatchSource_SetHandler_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOInterruptDispatchSource_SetHandler_Msg_With_Content * msg = &buf.msg;
    struct IOInterruptDispatchSource_SetHandler_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOInterruptDispatchSource_SetHandler_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IOInterruptDispatchSource_SetHandler_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 2;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->action__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.action = (OSObjectRef) action;

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
            if (rpl->content.__hdr.msgid                  != IOInterruptDispatchSource_SetHandler_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 0) { ret = kIOReturnIPCError; break; };
            if (IOInterruptDispatchSource_SetHandler_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
    }


    return (ret);
}

kern_return_t
IOInterruptDispatchSource::GetLastInterrupt(
        uint64_t * count,
        uint64_t * time,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOInterruptDispatchSource_GetLastInterrupt_Msg_With_Content msg;
        struct
        {
            IOInterruptDispatchSource_GetLastInterrupt_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOInterruptDispatchSource_GetLastInterrupt_Msg_With_Content * msg = &buf.msg;
    struct IOInterruptDispatchSource_GetLastInterrupt_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOInterruptDispatchSource_GetLastInterrupt_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IOInterruptDispatchSource_GetLastInterrupt_Msg_ObjRefs;
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
            if (rpl->content.__hdr.msgid                  != IOInterruptDispatchSource_GetLastInterrupt_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 0) { ret = kIOReturnIPCError; break; };
            if (IOInterruptDispatchSource_GetLastInterrupt_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        if (count) *count = rpl->content.count;
        if (time) *time = rpl->content.time;
    }


    return (ret);
}

kern_return_t
IOInterruptDispatchSource::InterruptOccurred(
        IORPC rpc,
        OSAction * action,
        uint64_t count,
        uint64_t time,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    struct IOInterruptDispatchSource_InterruptOccurred_Msg_With_Content * msg = (typeof(msg)) rpc.reply;
#ifdef KERNEL
    rpc.kernelContent = &msg->content.__hdr;
#endif /* KERNEL */

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 1*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 1*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOInterruptDispatchSource_InterruptOccurred_ID;
    msg->content.__object = (OSObjectRef) action;
    msg->content.__hdr.objectRefs = IOInterruptDispatchSource_InterruptOccurred_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 2;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->action__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.action = (OSObjectRef) action;

    msg->content.count = count;

    msg->content.time = time;


    ret = kIOReturnSuccess;

    return (ret);
}

kern_return_t
IOInterruptDispatchSource::Create_Invoke(const IORPC _rpc,
        Create_Handler func)
{
    IOInterruptDispatchSource_Create_Invocation rpc = { _rpc };
    IOInterruptDispatchSource_Create_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOInterruptDispatchSource_Create_Msg *         message = rpc.message;
    const IOInterruptDispatchSource_Create_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOInterruptDispatchSource_Create_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;
    IOService * provider;
    IODispatchQueue * queue;

    if (3 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOInterruptDispatchSource_Create_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOInterruptDispatchSource_Create_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    provider = OSDynamicCast(IOService, (OSObject *) MESSAGE_CONTENT(provider));
    if (!provider && MESSAGE_CONTENT(provider)) return (kIOReturnBadArgument);
    queue = OSDynamicCast(IODispatchQueue, (OSObject *) MESSAGE_CONTENT(queue));
    if (!queue && MESSAGE_CONTENT(queue)) return (kIOReturnBadArgument);

    ret = (*func)(        provider,
        MESSAGE_CONTENT(index),
        queue,
        (IOInterruptDispatchSource **)&reply->content.source);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOInterruptDispatchSource_Create_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 1;
    reply->content.__hdr.objectRefs = IOInterruptDispatchSource_Create_Rpl_ObjRefs;
    reply->source__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    return (ret);
}

kern_return_t
IOInterruptDispatchSource::GetInterruptType_Invoke(const IORPC _rpc,
        GetInterruptType_Handler func)
{
    IOInterruptDispatchSource_GetInterruptType_Invocation rpc = { _rpc };
    IOInterruptDispatchSource_GetInterruptType_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOInterruptDispatchSource_GetInterruptType_Msg *         message = rpc.message;
    const IOInterruptDispatchSource_GetInterruptType_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOInterruptDispatchSource_GetInterruptType_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;
    IOService * provider;

    if (2 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOInterruptDispatchSource_GetInterruptType_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOInterruptDispatchSource_GetInterruptType_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    provider = OSDynamicCast(IOService, (OSObject *) MESSAGE_CONTENT(provider));
    if (!provider && MESSAGE_CONTENT(provider)) return (kIOReturnBadArgument);

    ret = (*func)(        provider,
        MESSAGE_CONTENT(index),
        &reply->content.interruptType);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOInterruptDispatchSource_GetInterruptType_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 0;
    reply->content.__hdr.objectRefs = IOInterruptDispatchSource_GetInterruptType_Rpl_ObjRefs;

    return (ret);
}

kern_return_t
IOInterruptDispatchSource::SetHandler_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        SetHandler_Handler func)
{
    IOInterruptDispatchSource_SetHandler_Invocation rpc = { _rpc };
    IOInterruptDispatchSource_SetHandler_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOInterruptDispatchSource_SetHandler_Msg *         message = rpc.message;
    const IOInterruptDispatchSource_SetHandler_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOInterruptDispatchSource_SetHandler_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;
    OSAction * action;

    if (2 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOInterruptDispatchSource_SetHandler_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOInterruptDispatchSource_SetHandler_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    action = OSDynamicCast(OSAction, (OSObject *) MESSAGE_CONTENT(action));
    if (!action && MESSAGE_CONTENT(action)) return (kIOReturnBadArgument);

    ret = (*func)(target,
        action);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOInterruptDispatchSource_SetHandler_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 0;
    reply->content.__hdr.objectRefs = IOInterruptDispatchSource_SetHandler_Rpl_ObjRefs;

    return (ret);
}

kern_return_t
IOInterruptDispatchSource::GetLastInterrupt_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        GetLastInterrupt_Handler func)
{
    IOInterruptDispatchSource_GetLastInterrupt_Invocation rpc = { _rpc };
    IOInterruptDispatchSource_GetLastInterrupt_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOInterruptDispatchSource_GetLastInterrupt_Msg *         message = rpc.message;
    const IOInterruptDispatchSource_GetLastInterrupt_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOInterruptDispatchSource_GetLastInterrupt_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;

    if (1 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOInterruptDispatchSource_GetLastInterrupt_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOInterruptDispatchSource_GetLastInterrupt_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);

    ret = (*func)(target,
        &reply->content.count,
        &reply->content.time);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOInterruptDispatchSource_GetLastInterrupt_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 0;
    reply->content.__hdr.objectRefs = IOInterruptDispatchSource_GetLastInterrupt_Rpl_ObjRefs;

    return (ret);
}

kern_return_t
IOInterruptDispatchSource::InterruptOccurred_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        InterruptOccurred_Handler func)
{
    return IOInterruptDispatchSource::InterruptOccurred_Invoke(_rpc, target, func, NULL);
}

kern_return_t
IOInterruptDispatchSource::InterruptOccurred_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        InterruptOccurred_Handler func,
        const OSMetaClass * targetActionClass)
{
    IOInterruptDispatchSource_InterruptOccurred_Invocation rpc = { _rpc };
    IOInterruptDispatchSource_InterruptOccurred_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOInterruptDispatchSource_InterruptOccurred_Msg *         message = rpc.message;
    const IOInterruptDispatchSource_InterruptOccurred_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOInterruptDispatchSource_InterruptOccurred_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
    OSAction * action;

    if (2 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOInterruptDispatchSource_InterruptOccurred_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOInterruptDispatchSource_InterruptOccurred_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    if (targetActionClass) {
        action = (OSAction *) OSMetaClassBase::safeMetaCast((OSObject *) MESSAGE_CONTENT(action), targetActionClass);
    } else {
        action = OSDynamicCast(OSAction, (OSObject *) MESSAGE_CONTENT(action));
    }
    if (!action && MESSAGE_CONTENT(action)) return (kIOReturnBadArgument);

    (*func)(target,
        action,
        MESSAGE_CONTENT(count),
        MESSAGE_CONTENT(time));


    return (kIOReturnSuccess);
}



